# 看板描述 JSON 格式

`dashboard_kit.py review --spec` 读取下面的格式。完整示例见 [`assets/example_spec.json`](../assets/example_spec.json)。没有的字段留空，脚本会把缺失本身当作问题列出来，不要为了得分编造。

| 字段 | 说明 |
| --- | --- |
| `name` | 看板名称 |
| `audience` | 目标受众 |
| `decisions` | 看板要支持的决策，1 到 3 条 |
| `refresh` | 刷新频率和数据延迟 |
| `owner` | 负责人 |
| `filters` | 全局筛选项 |
| `modules[].name` | 模块名称，必填 |
| `modules[].question` | 这个模块回答什么问题 |
| `modules[].chart` | `kpi`、`line`、`bar`、`table`、`pie`、`dual_axis`、`gauge`、`pie_3d` 等 |
| `modules[].categories` | 饼图的分类数 |
| `modules[].level` | `primary` 主指标、`process` 过程指标、`explain` 解释指标、`guardrail` 护栏指标 |
| `modules[].metrics` | `[{"name", "definition"}]` |
| `modules[].dimensions` | 可以拆解的维度 |
| `modules[].drilldown` | 下钻路径 |
| `modules[].action` | 主指标异常时谁做什么 |

## 评分

五个维度各 2 分，满分 10 分：决策服务、指标层级、图表匹配、定位与行动、数据可信。

| 结果 | code | 含义 |
| --- | --- | --- |
| 有 P0 或低于 5 分 | `rework` | 不能支持决策，先重新梳理目标和指标 |
| 5 到 7 分 | `revise` | 结构可用，按问题清单修改后上线 |
| 8 分及以上 | `ok` | 结构基本合格，业务判断仍需人工审查 |

## 改版原型

在 spec 中加入 `redesign`，脚本用 `--html` 渲染成自包含原型：

```json
{
  "redesign": {
    "title": "看板名称（改版原型）",
    "headline": "这版看板想解决什么",
    "kpis": [{"label": "GMV", "value": "待接入", "note": "主指标"}],
    "sections": [{
      "title": "第二屏：定位问题",
      "lead": "这一屏的读图路径",
      "rows": [
        {"chart": "bar", "title": "图表标题", "question": "回答的问题", "categories": ["A", "B"], "values": [1, 2], "fmt": "num"},
        {"chart": "line", "title": "趋势", "categories": ["周一", "周二"], "series": [{"name": "本周", "values": [1, 2]}]},
        {"chart": "paired_bar", "title": "两期对比", "categories": ["A"], "current": [1], "baseline": [2]},
        {"chart": "diverging", "title": "贡献拆解", "categories": ["A", "B"], "values": [1, -1]},
        {"chart": "table", "title": "明细", "headers": ["列"], "rows": [["值"]]}
      ]
    }]
  }
}
```

原型里的数字只能来自用户材料。没有真实数据时，`values` 留空，页面显示“暂无数据”；指标卡写“待接入”。
