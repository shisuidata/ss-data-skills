#!/usr/bin/env python3
"""实时管道容量估算：State、Kafka、Checkpoint（仅依赖 Python 标准库）。

  python3 estimate.py state --keys 5000000 --value-bytes 200 --parallelism 20
  python3 estimate.py kafka --peak-qps 5000 --message-bytes 800 --retention-days 3
  python3 estimate.py checkpoint --state-gb 40 --interval-s 300 --changed-ratio 0.2 --upload-mbps 200

所有结果都是数量级估算，用来发现明显不合理的配置，上线前必须压测。
"""

from __future__ import annotations

import argparse
import json
import math
import sys

GB = 1024 ** 3
MB = 1024 ** 2
SECONDS_PER_DAY = 86400
LARGE_TASK_STATE_GB = 20


def emit(result: dict) -> int:
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    if args.keys <= 0 or args.value_bytes <= 0 or args.parallelism <= 0:
        raise SystemExit("--keys、--value-bytes、--parallelism 必须大于 0")
    per_key = (args.value_bytes + args.key_overhead_bytes) * args.windows_per_key
    raw = args.keys * per_key
    on_disk = raw * args.rocksdb_factor
    per_task = on_disk / args.parallelism
    checks = []
    if per_task / GB > LARGE_TASK_STATE_GB:
        checks.append({"id": "large_task_state", "status": "warn", "title": f"单 Task State 约 {per_task / GB:.1f} GB，恢复和扩缩容会很慢",
                       "detail": "提高并行度、缩短 TTL，或把长窗口聚合放到离线层"})
    if args.windows_per_key > 1:
        checks.append({"id": "windows", "status": "info", "title": f"每个 Key 按 {args.windows_per_key} 个并存窗口估算", "detail": "滑动窗口的并存窗口数约等于 窗口大小 / 滑动步长"})
    checks.append({"id": "key_definition", "status": "info", "title": "--keys 应为 TTL 内出现过的不同 Key 数",
                   "detail": "不是日活。TTL 为 7 天时，7 天累计的不同用户数通常明显大于单日活跃"})
    return emit({"keys": args.keys, "bytes_per_key": per_key, "state_raw_gb": raw / GB, "state_on_disk_gb": on_disk / GB, "state_per_task_gb": per_task / GB,
                 "parallelism": args.parallelism, "assumptions": {"key_overhead_bytes": args.key_overhead_bytes, "rocksdb_factor": args.rocksdb_factor}, "checks": checks})


def cmd_kafka(args: argparse.Namespace) -> int:
    if args.peak_qps <= 0 or args.message_bytes <= 0:
        raise SystemExit("--peak-qps、--message-bytes 必须大于 0")
    peak_mb = args.peak_qps * args.message_bytes / MB
    average_qps = args.average_qps or args.peak_qps * args.average_ratio
    by_throughput = math.ceil(peak_mb / args.partition_mbps)
    partitions = max(by_throughput, args.consumer_parallelism, 3)
    storage = average_qps * args.message_bytes * SECONDS_PER_DAY * args.retention_days * args.replication / args.compression_ratio
    checks = []
    if args.consumer_parallelism and args.consumer_parallelism > by_throughput:
        checks.append({"id": "partitions", "status": "info", "title": "分区数由消费并行度决定", "detail": "分区数小于消费并行度时，多余的消费者会空闲"})
    checks.append({"id": "key_skew", "status": "info", "title": "这里假设 Key 分布均匀", "detail": "热点 Key 会让单分区成为瓶颈，需要结合 Key 分布确认"})
    return emit({"peak_throughput_mb_s": peak_mb, "partitions_recommended": partitions, "partitions_by_throughput": by_throughput,
                 "average_qps": average_qps, "storage_gb": storage / GB, "assumptions": {"partition_mbps": args.partition_mbps, "replication": args.replication, "compression_ratio": args.compression_ratio},
                 "checks": checks})


def cmd_checkpoint(args: argparse.Namespace) -> int:
    if args.upload_mbps <= 0 or args.interval_s <= 0:
        raise SystemExit("--upload-mbps、--interval-s 必须大于 0")
    upload_mb = args.state_gb * 1024 * (args.changed_ratio if args.incremental else 1.0)
    duration = upload_mb / args.upload_mbps
    utilisation = duration / args.interval_s
    checks = []
    if utilisation > 0.5:
        checks.append({"id": "too_long", "status": "fail", "title": f"Checkpoint 预计 {duration:.0f} 秒，占间隔的 {utilisation:.0%}",
                       "detail": "容易超时或连续失败。拉长间隔、开启增量 Checkpoint、提高上传带宽，或减小 State"})
    elif utilisation > 0.2:
        checks.append({"id": "tight", "status": "warn", "title": f"Checkpoint 预计占间隔的 {utilisation:.0%}", "detail": "高峰期背压时可能超时，建议预留余量"})
    return emit({"upload_mb": upload_mb, "estimated_duration_s": duration, "interval_s": args.interval_s, "utilisation": utilisation, "incremental": args.incremental,
                 "recommended_min_interval_s": math.ceil(duration * 5), "checks": checks,
                 "limits": ["没有计入对齐时间和背压，高峰期实际耗时会更长"]})


def main() -> int:
    parser = argparse.ArgumentParser(description="实时管道容量估算（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("state", help="估算 State 大小")
    s.add_argument("--keys", type=int, required=True, help="TTL 内的不同 Key 数")
    s.add_argument("--value-bytes", type=int, required=True, help="每个 Key 的状态大小")
    s.add_argument("--parallelism", type=int, default=1)
    s.add_argument("--windows-per-key", type=int, default=1, help="每个 Key 并存的窗口数，滑动窗口约为 窗口大小 / 步长")
    s.add_argument("--key-overhead-bytes", type=int, default=64, help="Key 和序列化的额外开销")
    s.add_argument("--rocksdb-factor", type=float, default=1.5, help="RocksDB 空间放大系数，默认 1.5")
    s.set_defaults(func=cmd_state)

    k = sub.add_parser("kafka", help="估算 Kafka 分区数和存储")
    k.add_argument("--peak-qps", type=float, required=True, help="峰值消息数 / 秒")
    k.add_argument("--message-bytes", type=int, required=True, help="单条消息大小")
    k.add_argument("--average-qps", type=float, help="平均消息数 / 秒，不填时按峰值乘 --average-ratio")
    k.add_argument("--average-ratio", type=float, default=0.3, help="平均与峰值之比，默认 0.3")
    k.add_argument("--retention-days", type=float, default=3)
    k.add_argument("--replication", type=int, default=3)
    k.add_argument("--compression-ratio", type=float, default=2.0, help="压缩比，默认 2")
    k.add_argument("--partition-mbps", type=float, default=10, help="单分区可承载 MB/s，默认 10，需要按集群实测调整")
    k.add_argument("--consumer-parallelism", type=int, default=0, help="消费端计划的并行度")
    k.set_defaults(func=cmd_kafka)

    c = sub.add_parser("checkpoint", help="估算 Checkpoint 耗时是否合理")
    c.add_argument("--state-gb", type=float, required=True)
    c.add_argument("--interval-s", type=float, required=True, help="Checkpoint 间隔（秒）")
    c.add_argument("--upload-mbps", type=float, default=200, help="上传到分布式存储的总带宽 MB/s，默认 200")
    c.add_argument("--changed-ratio", type=float, default=0.2, help="增量 Checkpoint 每次变化的比例，默认 0.2")
    c.add_argument("--full", dest="incremental", action="store_false", help="按全量 Checkpoint 估算，默认增量")
    c.set_defaults(func=cmd_checkpoint, incremental=True)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
