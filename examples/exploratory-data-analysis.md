# exploratory-data-analysis 示例

## 适用场景

刚拿到一份数据，不确定字段是否可用、质量是否可靠、后续应该分析什么。

## 示例输入

```text
请用 exploratory-data-analysis 分析下面这张用户行为表：

粒度：一行一条用户事件
字段：
- user_id
- event_time
- event_name
- page
- channel
- device
- session_id

目标：判断是否能用于用户转化路径分析。
```

## 预期输出

```markdown
## EDA 结果

### 数据概览

| 项目 | 结果 |
| --- | --- |
| 数据对象 | 用户行为事件 |
| 数据粒度 | 一行一条事件 |
| 主键候选 | session_id + event_time + event_name，需验证 |
| 核心时间字段 | event_time |

### 数据质量问题

| 风险等级 | 问题 | 影响 | 建议 |
| --- | --- | --- | --- |
| P1 | session_id 可能缺失 | 无法稳定还原路径 | 统计缺失率 |
| P1 | event_time 可能存在乱序 | 影响漏斗顺序 | 检查同用户事件时间 |
| P2 | page 和 event_name 语义可能重叠 | 路径解释困难 | 建事件字典 |

### 可继续分析方向

- 注册到支付的事件路径
- 不同渠道的关键步骤流失
- 移动端和桌面端路径差异
```

## 使用说明

EDA 的输出不是最终报告，而是告诉你这份数据能不能继续分析，以及下一步怎么分析。

