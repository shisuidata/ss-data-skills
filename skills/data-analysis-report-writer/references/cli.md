# 命令行参数

这份文档由脚本的参数定义生成，修改参数后请重新生成，不要手改。所有脚本都把结果以 JSON 打印到标准输出。

## `report.py refs`

列出来源中可引用的数字和建议写法

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--source`（可重复） | 是 | — | source_help |
| `--grep` | 否 | — | 只显示路径包含该文本的条目 |
| `--strings`（开关） | 否 | — | 同时列出文本字段 |
| `--limit` | 否 | 200 | — |

## `report.py skeleton`

根据来源生成报告规格草稿

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--source`（可重复） | 是 | — | source_help |
| `--out` | 否 | — | 写入文件（同时打印到标准输出） |

## `report.py build`

规格 → HTML / Markdown 报告，并检查证据与数字溯源

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--spec` | 是 | — | 报告规格 JSON（见 references/spec-schema.md） |
| `--source`（可重复） | 否 | — | source_help + "；覆盖 spec.sources 中的同名来源" |
| `--html` | 否 | — | 输出 HTML 路径 |
| `--md` | 否 | — | 输出 Markdown 路径（便于粘贴到文档） |
| `--strict`（开关） | 否 | — | 有未溯源数字或规格警告时返回非 0 |

## `report.py lint`

检查手写 Markdown 报告里的数字能否在来源中找到

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--text` | 是 | — | Markdown 报告路径 |
| `--source`（可重复） | 否 | — | source_help |
| `--facts` | 否 | — | 补充事实 JSON：{名称: 数值 或 {value, source}} |
