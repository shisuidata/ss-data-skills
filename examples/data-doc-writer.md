# data-doc-writer 示例

## 适用场景

一张表、一个指标或一个数据任务需要交接给其他人维护，或者需要沉淀到团队知识库。

## 示例输入

```text
请用 data-doc-writer 为下面这张 SaaS 激活明细表写数据文档。

表名：dws_user_activation_1d
主题域：用户增长
用途：统计新注册用户在注册后 7 天内的激活动作完成情况。
粒度：register_date + channel + user_id。
更新频率：每天 8 点产出上一日数据。
保留周期：730 天。

字段：
- register_date string 注册日期
- user_id string 用户 ID
- channel string 注册渠道
- create_workspace_flag int 是否创建工作区
- invite_member_flag int 是否邀请成员
- complete_task_flag int 是否完成核心任务
- activated_flag int 是否激活，任意两个 flag 为 1 即激活

上游：
- dwd_user_register_d
- dwd_user_behavior_d

下游：
- 激活率看板
- 增长周报
- 新版引导页 A/B 实验分析

请输出可交接的 Markdown 文档，并列出待补充信息。
```

## 预期输出

```markdown
# 数据文档：dws_user_activation_1d

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| 主题域 | 用户增长 |
| 数据粒度 | register_date + channel + user_id |
| 更新频率 | 每天 8 点产出上一日数据 |
| 保留周期 | 730 天 |

## 2. 业务用途

用于分析新注册用户在注册后 7 天内是否完成核心激活动作，支撑激活率看板、增长周报和实验分析。

## 3. 字段字典

| 字段 | 类型 | 含义 | 注意事项 |
| --- | --- | --- | --- |
| activated_flag | int | 是否激活 | create_workspace、invite_member、complete_task 任意两个为 1 |

## 4. 生产逻辑

从注册表获取新用户，从行为表统计注册后 7 天内的三个关键动作，并按用户生成激活标记。

## 5. 常见误用与风险

- 不要把用户粒度直接汇总成账户粒度。
- 7 日窗口未完整时，不应直接计算最终激活率。
- channel 是注册渠道，不一定等同于付费归因渠道。

## 6. 待补充信息

- 主键或唯一性约束。
- 分区字段。
- SLA 和质量规则。
- 字段枚举值和空值处理规则。
```

## 使用说明

这个示例展示了 `data-doc-writer` 不只是整理字段，而是要写清用途、粒度、逻辑、风险和待补充信息。
