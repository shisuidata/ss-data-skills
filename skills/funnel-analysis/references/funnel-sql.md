# 漏斗 SQL 模板

数据量大时，在仓库里算出有序漏斗人数，再把结果写成汇总 JSON 交给脚本。

## 最常见的错误写法

```sql
-- 错误：每一步独立去重，不要求先完成上一步
SELECT
  COUNT(DISTINCT CASE WHEN event_name = 'register_success' THEN user_id END) AS step1,
  COUNT(DISTINCT CASE WHEN event_name = 'product_view'     THEN user_id END) AS step2,
  COUNT(DISTINCT CASE WHEN event_name = 'add_to_cart'      THEN user_id END) AS step3
FROM dwd_user_event_d
WHERE dt BETWEEN '2026-05-01' AND '2026-05-14';
```

问题：

- 老用户、没有注册事件的用户也会计入后续步骤，后一步人数甚至可能多于前一步
- 没有顺序：先加购后浏览的用户也被算作“浏览后加购”
- 按事件日期而不是入口日期切时期：5 月 14 日注册、5 月 15 日支付的用户，支付被漏掉

## 通用写法（Spark SQL / Hive / PostgreSQL，按引擎调整时间运算）

思路：先找每个用户的入口时间，再逐步找“上一步之后、窗口之内”的最早事件。

```sql
WITH s1 AS (                                    -- 入口：按入口时间划分时期
  SELECT user_id, MIN(event_time) AS t1
  FROM dwd_user_event_d
  WHERE event_name = 'register_success'
    AND dt BETWEEN '2026-05-01' AND '2026-05-14'
  GROUP BY user_id
),
s2 AS (
  SELECT s1.user_id, s1.t1, MIN(e.event_time) AS t2
  FROM s1
  JOIN dwd_user_event_d e
    ON e.user_id = s1.user_id
   AND e.event_name = 'product_view'
   AND e.event_time >= s1.t1
   AND e.event_time <= s1.t1 + INTERVAL 7 DAYS  -- 转化窗口（PostgreSQL: INTERVAL '7 days'）
  WHERE e.dt BETWEEN '2026-05-01' AND '2026-05-21' -- 分区上界 = 时期结束 + 窗口
  GROUP BY s1.user_id, s1.t1
),
s3 AS (
  SELECT s2.user_id, s2.t1, MIN(e.event_time) AS t3
  FROM s2
  JOIN dwd_user_event_d e
    ON e.user_id = s2.user_id
   AND e.event_name = 'add_to_cart'
   AND e.event_time >= s2.t2
   AND e.event_time <= s2.t1 + INTERVAL 7 DAYS
  WHERE e.dt BETWEEN '2026-05-01' AND '2026-05-21'
  GROUP BY s2.user_id, s2.t1
)
SELECT
  u.channel_id,
  COUNT(s1.user_id) AS step1,
  COUNT(s2.user_id) AS step2,
  COUNT(s3.user_id) AS step3
FROM s1
LEFT JOIN s2 ON s2.user_id = s1.user_id
LEFT JOIN s3 ON s3.user_id = s1.user_id
LEFT JOIN dim_user u ON u.user_id = s1.user_id
GROUP BY u.channel_id;                         -- 去掉 GROUP BY 得到整体行
```

注意：

- 每一步都要带分区过滤，否则全表扫描
- 时期内最晚进入的用户可能还没走完窗口：要么只统计 `t1 <= 数据截止时间 - 窗口` 的用户，要么等窗口结束再算
- 统计对象是企业、设备时，把 `user_id` 换成对应主键

## ClickHouse：windowFunnel

```sql
SELECT
  level,
  count() AS users
FROM (
  SELECT
    user_id,
    minIf(event_time, event_name = 'register_success') AS entry_time,
    windowFunnel(7 * 86400)(
      event_time,
      event_name = 'register_success',
      event_name = 'product_view',
      event_name = 'add_to_cart',
      event_name = 'order_submit',
      event_name = 'pay_success'
    ) AS level
  FROM dwd_user_event_d
  WHERE dt BETWEEN '2026-05-01' AND '2026-05-21'
  GROUP BY user_id
)
WHERE level > 0
  AND entry_time >= '2026-05-01 00:00:00'
  AND entry_time <  '2026-05-15 00:00:00'
GROUP BY level
ORDER BY level;
```

`level` 是用户最远到达的步骤。到达第 k 步的人数 = `level >= k` 的用户数之和，转换成 `counts` 时要做一次逆向累加。窗口单位与时间列类型一致（DateTime 为秒）。

Doris、StarRocks 也提供 `window_funnel` 函数，但参数顺序和条件写法与 ClickHouse 不同，使用前以对应版本的官方文档为准。

## 转成汇总 JSON

```json
{"period": "本期", "counts": [step1, step2, step3]}
{"period": "本期", "segment": {"channel_id": "channel_a"}, "counts": [ ... ]}
```

完整格式见 [输入格式](input-schema.md)。
