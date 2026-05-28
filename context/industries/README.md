# 行业上下文包

行业上下文包用于给通用 Skill 补充业务语境。

我们的原则是：

```text
通用 Skill 负责方法，行业上下文负责业务语义。
```

例如 `business-root-cause-analysis` 在电商、SaaS、内容社区中都可以使用，但异常指标、业务实体、归因维度和可行动建议会明显不同。

## 当前行业包

| 行业 | 适用场景 |
| --- | --- |
| [电商](ecommerce.md) | GMV、订单、转化、渠道、商品、退款、库存、活动 |
| [SaaS](saas.md) | MRR、ARR、激活、试用转付费、续费、流失、席位 |
| [内容社区](content-community.md) | DAU、留存、内容供给、曝光、点击、互动、创作者生态 |

## 使用方式

把行业上下文和具体 Skill 的上下文模板一起使用。

```text
请使用 business-root-cause-analysis 分析下面的问题。

行业上下文：
[粘贴 context/industries/saas.md 中相关部分]

任务上下文：
[粘贴 context/templates/analysis-context.md 并填写]
```

## 维护规则

- 行业包只写通用业务知识，不写某家公司内部信息。
- 指标口径给出常见写法，但必须允许用户覆盖。
- 不同行业包可以复用同一个 Skill，不要为每个行业复制一份 Skill。
- 如果某个行业差异已经影响工作流程，再考虑新增行业专用 Skill。
