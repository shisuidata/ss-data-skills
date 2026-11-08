# 命令行参数

这份文档由脚本的参数定义生成，修改参数后请重新生成，不要手改。所有脚本都把结果以 JSON 打印到标准输出。

## `lineage.py impact`

计算某个对象变更的下游影响

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--edges` | 否 | — | 边表 CSV：upstream, downstream，可选 upstream_column |
| `--manifest` | 否 | — | dbt 的 target/manifest.json |
| `--assets` | 否 | — | 资产 CSV：name, type, owner, importance |
| `--target` | 是 | — | 变更对象：表名，字段级写成 表名:字段名 |
| `--change` | 是 | — | 变更类型。可选：sorted(CHANGES |
| `--max-depth` | 否 | — | 最多追溯的层数，默认不限 |
| `--json` | 否 | — | 同时把 JSON 写入文件 |

## `lineage.py edges`

从 SQL 文件提取表级血缘

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--sql`（可重复） | 是 | — | SQL 文件路径，可重复 |
| `--out` | 否 | — | 输出边表 CSV |
