# 命令行参数

这份文档由脚本的参数定义生成，修改参数后请重新生成，不要手改。所有脚本都把结果以 JSON 打印到标准输出。

## `dashboard_kit.py review`

结构审查并生成改版原型

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--spec` | 是 | — | 看板描述 JSON，见 references/spec-format.md |
| `--html` | 否 | — | 输出改版原型 HTML |
| `--json` | 否 | — | 同时把 JSON 写入文件 |
