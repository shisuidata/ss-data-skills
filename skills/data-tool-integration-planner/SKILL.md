---
name: data-tool-integration-planner
description: Use when planning integration with databases, BI tools, data platforms, APIs, workflow systems, storage services, or third-party tools, including connection requirements, API availability, auth strategy, configuration questions, and validation steps.
---

# Data Tool Integration Planner

## 目标

帮助用户把“我要接一个工具或数据库”拆成可配置、可验证、可交付的集成方案。

这个 Skill 是基础 Infra 类 Skill，服务于数据库、API、BI、调度、存储、消息通知等工具对接。

## 使用场景

使用这个 Skill，当用户需要：

- 连接 MySQL、PostgreSQL、ClickHouse、Hive、Spark、Doris、StarRocks 等数据库或数仓
- 对接 BI、调度平台、数据质量平台、工单系统、飞书/钉钉/企业微信等三方工具
- 判断某个工具是否有 API、Webhook、JDBC/ODBC、CLI 或导出能力
- 设计配置表、连接参数、权限、密钥和环境变量
- 为自动化工作流准备可复用的工具接入上下文

## 不适用场景

不要使用这个 Skill 处理：

- 实际保存明文密码、Token 或密钥
- 在没有授权的情况下连接生产数据库
- 写完整业务 SQL，应使用 `sql-reviewer`
- 设计数据表，应使用 `table-design-advisor`
- 排查具体任务失败，应使用后续专门的 pipeline debug 类 Skill

## 输入信息

最少输入：

- 工具名称
- 工具类型：database、api、bi、workflow、storage、message
- 接入目标
- 当前已知连接方式

推荐输入：

- 是否有官方 API、Webhook、JDBC/ODBC、CLI、SDK
- 环境：dev、test、prod
- 认证方式：账号密码、Token、OAuth、AK/SK、服务账号、内网免密
- 网络要求：公网、内网、VPN、白名单、堡垒机
- 权限范围：只读、写入、管理、回调
- 数据范围和频率
- 安全要求：密钥管理、脱敏、审计、最小权限

## 上下文建议

优先使用这些模板准备上下文：

- [工具集成上下文模板](../../context/templates/tool-integration-context.md)
- [通用数据任务上下文](../../context/templates/data-task-context.md)
- [SQL 审查上下文模板](../../context/templates/sql-review-context.md)

如果用户不能确认工具是否有 API，应先让用户补充官方文档、控制台截图或接口说明；没有证据时只能列出待确认问题。

## 可用脚本

本 Skill 附带一个配置校验脚本：

```bash
node skills/data-tool-integration-planner/scripts/validate_integration_config.mjs <config.json>
```

脚本只做本地 JSON 结构校验，不连接真实服务，不读取密钥值。

## 工作流程

1. 识别工具类型和接入目标。
2. 判断可用接入方式：API、Webhook、JDBC/ODBC、CLI、SDK、文件导出。
3. 列出必须向用户确认的配置项。
4. 设计安全配置：环境变量、密钥引用、最小权限、网络白名单。
5. 输出连接配置模板和验证步骤。
6. 对缺失 API 或无法直连的工具，给出替代方案：文件导出、Webhook、中转服务或人工上传。

## 输出格式

```markdown
## 集成方案结论

## 工具与接入目标

## API / 连接能力确认

| 能力 | 是否已确认 | 证据/待确认 |
| --- | --- | --- |

## 配置项清单

| 配置项 | 是否必填 | 示例 | 安全要求 |
| --- | --- | --- | --- |

## 权限与安全

## 验证步骤

## 配置模板

## 待用户确认问题
```

## 质量标准

输出必须：

- 不要求用户粘贴明文密码或 Token
- 对 API、Webhook、JDBC/ODBC、CLI 等能力标记“已确认”或“待确认”
- 给出最小权限建议
- 明确网络、认证、环境变量和审计要求
- 提供可复制的配置模板
- 不能假设某个工具一定有 API

## 示例 Prompt

```text
请用 data-tool-integration-planner 帮我规划一个数据库接入方案。

工具名称：PostgreSQL
工具类型：database
接入目标：读取演示环境中的订单和用户表，用于 SQL 审查和数据分析示例。
环境：demo
已知配置：
- host: pg-demo.internal
- port: 5432
- database: analytics_demo
- auth: 用户名 + 密码
安全要求：
- 不允许在文档中保存明文密码
- 只读权限
- 需要记录连接配置模板和验证步骤

请输出配置方案、待确认问题和本地配置 JSON 示例。
```
