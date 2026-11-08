# 命令行参数

这份文档由脚本的参数定义生成，修改参数后请重新生成，不要手改。所有脚本都把结果以 JSON 打印到标准输出。

## `estimate.py state`

估算 State 大小

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--keys` | 是 | — | TTL 内的不同 Key 数 |
| `--value-bytes` | 是 | — | 每个 Key 的状态大小 |
| `--parallelism` | 否 | 1 | — |
| `--windows-per-key` | 否 | 1 | 每个 Key 并存的窗口数，滑动窗口约为 窗口大小 / 步长 |
| `--key-overhead-bytes` | 否 | 64 | Key 和序列化的额外开销 |
| `--rocksdb-factor` | 否 | 1.5 | RocksDB 空间放大系数，默认 1.5 |

## `estimate.py kafka`

估算 Kafka 分区数和存储

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--peak-qps` | 是 | — | 峰值消息数 / 秒 |
| `--message-bytes` | 是 | — | 单条消息大小 |
| `--average-qps` | 否 | — | 平均消息数 / 秒，不填时按峰值乘 --average-ratio |
| `--average-ratio` | 否 | 0.3 | 平均与峰值之比，默认 0.3 |
| `--retention-days` | 否 | 3 | — |
| `--replication` | 否 | 3 | — |
| `--compression-ratio` | 否 | 2.0 | 压缩比，默认 2 |
| `--partition-mbps` | 否 | 10 | 单分区可承载 MB/s，默认 10，需要按集群实测调整 |
| `--consumer-parallelism` | 否 | 0 | 消费端计划的并行度 |

## `estimate.py checkpoint`

估算 Checkpoint 耗时是否合理

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--state-gb` | 是 | — | — |
| `--interval-s` | 是 | — | Checkpoint 间隔（秒） |
| `--upload-mbps` | 否 | 200 | 上传到分布式存储的总带宽 MB/s，默认 200 |
| `--changed-ratio` | 否 | 0.2 | 增量 Checkpoint 每次变化的比例，默认 0.2 |
| `--full`（开关） | 否 | — | 按全量 Checkpoint 估算，默认增量 |
