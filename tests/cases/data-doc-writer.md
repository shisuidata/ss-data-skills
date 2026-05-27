# 测试用例：数据文档写作

## Skill

`data-doc-writer`

## 测试目标

检查 Skill 是否能把表结构和业务逻辑整理成可交接的数据文档，并明确用途、粒度、字段、生产逻辑、风险和待补充信息。

## 测试输入

```text
请使用 data-doc-writer 为下面这张表写 Markdown 数据文档。

表名：dws_user_activation_1d
主题域：用户增长
行业上下文：SaaS
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

## 通过标准

- 必须包含基本信息、业务用途、数据粒度、字段字典、生产逻辑、上下游关系。
- 必须说明 activated_flag 的口径。
- 必须指出 7 日窗口未完整时不应直接计算最终激活率。
- 必须指出 channel 是注册渠道，不一定等于付费归因渠道。
- 必须列出待补充信息，例如分区字段、主键、SLA、质量规则。
- 不得编造负责人、调度任务名或不存在的字段。
