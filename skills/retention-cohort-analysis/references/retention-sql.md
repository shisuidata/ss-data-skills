# 留存 SQL 模板

数据量大时，在仓库里算出每个批次的留存人数，再写成汇总 JSON 交给脚本。

## 三个最常见的错误

```sql
-- 错误 1：用“今天的活跃用户里有多少是 7 天前注册的”代替 7 日留存
-- 错误 2：未成熟的批次（注册不足 7 天）也算 D7，结果被当成 0 或偏低
-- 错误 3：任意事件都算回访，推送到达、后台唤醒把留存抬高
```

## 通用写法：按日、第 N 天当天回访（Spark SQL / Hive，PostgreSQL 用 `date - date` 计算天数）

```sql
WITH cohort AS (
  SELECT user_id, MIN(TO_DATE(event_time)) AS cohort_date
  FROM dwd_user_event_d
  WHERE event_name = 'register_success'
    AND dt BETWEEN '2026-03-02' AND '2026-04-26'
  GROUP BY user_id
),
activity AS (
  SELECT DISTINCT user_id, TO_DATE(event_time) AS active_date
  FROM dwd_user_event_d
  WHERE event_name IN ('app_open', 'product_view')     -- 只算主动行为
    AND dt BETWEEN '2026-03-02' AND '2026-05-10'
),
joined AS (
  SELECT c.user_id, c.cohort_date, DATEDIFF(a.active_date, c.cohort_date) AS day_n
  FROM cohort c
  LEFT JOIN activity a ON a.user_id = c.user_id AND a.active_date > c.cohort_date
)
SELECT
  cohort_date,
  COUNT(DISTINCT user_id) AS size,
  CASE WHEN DATE_ADD(cohort_date, 1)  <= DATE '2026-05-10'
       THEN COUNT(DISTINCT CASE WHEN day_n = 1  THEN user_id END) END AS d1,
  CASE WHEN DATE_ADD(cohort_date, 7)  <= DATE '2026-05-10'
       THEN COUNT(DISTINCT CASE WHEN day_n = 7  THEN user_id END) END AS d7,
  CASE WHEN DATE_ADD(cohort_date, 30) <= DATE '2026-05-10'
       THEN COUNT(DISTINCT CASE WHEN day_n = 30 THEN user_id END) END AS d30
FROM joined
GROUP BY cohort_date
ORDER BY cohort_date;
```

- `CASE WHEN ... <= 数据截止日 THEN ... END` 让未成熟的单元格输出 `NULL`，对应 JSON 里的 `null`
- “N 天内回访”口径：把 `day_n = 7` 改为 `day_n BETWEEN 1 AND 7`
- 滚动 24 小时口径：用时间戳差 `FLOOR((unix_timestamp(active_time) - unix_timestamp(start_time)) / 86400)` 代替日期差，`activity` 里保留时间戳
- 按周：`cohort_date` 取所在周的周一，`day_n` 换成 `FLOOR(DATEDIFF(...) / 7)`；按月：用月份差
- 分群：`cohort` 里带上渠道等字段，`GROUP BY cohort_date, channel_id`

## ClickHouse

上面的通用写法在 ClickHouse 中同样适用，把 `TO_DATE` 换成 `toDate`、`DATEDIFF(a, b)` 换成 `dateDiff('day', b, a)`、`DATE_ADD(d, n)` 换成 `d + n` 即可。

ClickHouse 也提供 `retention(cond1, cond2, ...)` 聚合函数，但它的条件是针对每一行事件判断的，“相对起点第 N 天”需要先在子查询里算出每个用户的起点日期并关联到事件行，再写进条件。直接在同一层聚合里引用起点日期是无效的。
