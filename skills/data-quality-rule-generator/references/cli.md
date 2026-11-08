# 命令行参数

这份文档由脚本的参数定义生成，修改参数后请重新生成，不要手改。所有脚本都把结果以 JSON 打印到标准输出。

## `dq_rules.py generate`

生成质量规则

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--schema` | 否 | — | 表结构 JSON，见 references/schema-format.md |
| `--eda` | 否 | — | eda.py 的 JSON 输出，按体检结果推断规则 |
| `--table` | 否 | — | --eda 模式下要处理的表名 |
| `--partition` | 否 | — | --eda 模式下的分区字段 |
| `--biz-date` | 否 | :biz_date | 业务日期表达式，如 '${bizdate}'，默认 :biz_date |
| `--sql` | 否 | — | 输出 SQL 校验文件 |
| `--dbt` | 否 | — | 输出 dbt schema.yml（dbt 1.10.5 及以上的 arguments 写法） |
| `--dbt-legacy`（开关） | 否 | — | 改用 dbt 1.10.5 以前的平铺写法 |
| `--ge` | 否 | — | 输出 Great Expectations 1.x 规则集 JSON |
