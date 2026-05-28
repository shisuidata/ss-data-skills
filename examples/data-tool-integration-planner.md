# data-tool-integration-planner 示例

## 适用场景

需要让数据工作流连接数据库、API、BI、调度平台或消息工具，但还没有形成安全的配置方案。

## 示例输入

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

## 预期输出

````markdown
## 集成方案结论

可以按只读数据库连接方案推进，但不能在文档或配置中保存明文密码。账号和密码应通过环境变量注入。

## API / 连接能力确认

| 能力 | 是否已确认 | 证据/待确认 |
| --- | --- | --- |
| JDBC/SQL 连接 | 已知 | PostgreSQL 支持 |
| 网络连通 | 待确认 | 需要确认运行环境能访问 pg-demo.internal |
| 只读权限 | 待确认 | 需要 DBA 创建或确认只读账号 |

## 配置模板

```json
{
  "toolName": "PostgreSQL",
  "toolType": "database",
  "owner": "data-platform",
  "environment": "demo",
  "connection": {
    "engine": "postgresql",
    "host": "pg-demo.internal",
    "port": 5432,
    "database": "analytics_demo"
  },
  "auth": {
    "method": "password",
    "usernameEnv": "PG_DEMO_USER",
    "passwordEnv": "PG_DEMO_PASSWORD"
  },
  "permissions": {
    "mode": "read_only"
  }
}
```

## 验证步骤

1. 校验配置 JSON 结构。
2. 确认网络连通和白名单。
3. 使用只读账号执行 `select 1`。
4. 只允许访问示例所需表。
````

## 使用说明

这个示例强调安全边界：Skill 可以规划配置，但不能要求用户粘贴明文密码或 Token。
