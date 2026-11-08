# 集成配置 JSON 格式

`scripts/validate_integration_config.mjs` 校验下面的格式。完整示例见 [`assets/example_database_config.json`](../assets/example_database_config.json)。

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `toolName` | 是 | 工具名称 |
| `toolType` | 是 | `database`、`api`、`bi`、`workflow`、`storage`、`message`、`other` |
| `owner` | 是 | 负责人或团队 |
| `environment` | 是 | 环境，如 `dev`、`test`、`prod` |
| `connection` | 是 | 连接信息 |
| `connection.engine` / `host` / `port` / `database` | `database` 类型必填 | `port` 是数字 |
| `connection.baseUrl` | `api` 类型必填 | 接口地址 |
| `auth.method` | 是 | 认证方式 |
| `auth.usernameEnv` / `auth.passwordEnv` | `method=password` 时必填 | 环境变量名，不是密码本身 |
| `auth.tokenEnv` | `method=token` 时必填 | 环境变量名 |
| `permissions.mode` | 否 | 如 `read_only` |

## 明文凭据检查

脚本会扫描整份配置，发现下面的情况就报错，位置不限于 `auth`：

- 键名包含 password、pwd、secret、token、api key、access key、private key、credential、authorization、cookie，且取值不是引用
- 连接 URL 里带密码，如 `postgres://user:pass@host/db`
- 取值里有 `Bearer xxx` 或 `Basic xxx`

下面这些写法视为引用，不会报错：

- 键名以 `Env`、`Ref`、`Url`、`Endpoint`、`Name`、`Path`、`File` 等结尾，如 `passwordEnv`、`tokenEndpoint`
- 取值是 `${VAR}`、`$VAR`、`env:VAR`、`vault:path`、`secretsmanager:name`

这个检查只能拦截常见写法。配置文件仍然不要放进代码仓库的公开位置。
