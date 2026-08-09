# AI Balance Monitor

轻量级 AI 中转站余额监控面板，支持 NewAPI 与 Sub2API，多站点定时检测、低余额告警和 Telegram 通知。

项目使用 **FastAPI + SQLite + APScheduler**，不依赖 MySQL、Redis 或独立任务队列，适合单机 Docker 部署。

## 功能特性

- 支持多个 NewAPI / Sub2API 站点
- 支持定时检测余额，也支持手动立即检查
- 支持低余额阈值告警和连续失败告警
- 支持 Telegram Bot 推送通知
- 支持列表、卡片、简洁卡片三种后台视图
- 支持自定义排序、按余额/状态/时间排序
- 支持一键打开中转站后台
- 支持自定义余额接口路径、余额字段路径、认证 Header 和额外 Header
- SQLite 本地持久化，不使用 MySQL
- Docker / Docker Compose 一键部署
- Web 后台默认端口 `8080`

## 界面

后台是一个轻量监控台：

- 左侧显示站点总览、正常数、低余额数、异常数
- 右侧显示监控站点，支持列表模式、卡片模式、简洁卡片模式
- 站点访问令牌在列表中始终脱敏
- 修改已有站点时会二次确认，避免误操作

## 快速部署

```bash
git clone https://github.com/youzi-x/ai-balance-monitor.git
cd ai-balance-monitor
cp .env.example .env
```

国内访问也可以使用 Gitee 镜像：

```bash
git clone https://gitee.com/shisongzhi/ai-balance-monitor.git
cd ai-balance-monitor
cp .env.example .env
```

编辑 `.env`，至少修改后台账号密码：

```dotenv
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-a-strong-password
```

启动：

```bash
docker compose up -d --build
```

访问：

```text
http://服务器IP:8080
```

浏览器会弹出 Basic Auth 登录框，输入 `.env` 中的 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`。

查看日志：

```bash
docker compose logs -f
```

停止服务：

```bash
docker compose down
```

SQLite 数据库位于 `./data/balance_monitor.db`，升级或迁移前备份整个 `data` 目录即可。

## 本地运行

要求 Python 3.11 或更新版本。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.init_db
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Windows PowerShell：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.init_db
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## NewAPI 配置

进入后台，点击“添加站点”：

| 字段 | 推荐值 |
| --- | --- |
| 类型 | `NewAPI` |
| 站点地址 | `https://newapi.example.com` |
| 访问令牌 | NewAPI 用户 Access Token / Dashboard Bearer Token |
| 余额接口路径 | `/api/user/self` |
| 认证方式 | `Bearer Token` |
| 认证 Header | `Authorization` |
| 认证前缀 | `Bearer` |
| 余额字段路径 | 留空，自动识别 |
| 额度除数 | `500000` |

NewAPI `/api/user/self` 返回的 `data.quota` 通常是额度单位；监控器默认用 `500000` 换算成显示余额。若你的站点采用不同的 `QuotaPerUnit`，请改为实际值。

如果你的 NewAPI 定制版本要求 `New-Api-User` 请求头，请在“额外 Header JSON”中填写：

```json
{"New-Api-User":"你的用户ID"}
```

## Sub2API 配置

Sub2API 默认使用平台 API Key 查询 `GET /v1/usage`，不需要后台登录后的 JWT。请填写你平时调用模型用的 `sk-...`：

| 字段 | 推荐值 |
| --- | --- |
| 类型 | `Sub2API` |
| 站点地址 | `https://sub2api.example.com`，不要带 `/v1` |
| 访问令牌 | Sub2API 平台 API Key，例如 `sk-...` |
| 余额接口路径 | `/v1/usage` |
| 认证方式 | `Bearer Token` |
| 认证 Header | `Authorization` |
| 认证前缀 | `Bearer` |
| 余额字段路径 | 留空，自动识别 `quota.remaining`、`remaining`、`balance` 等 |
| 额度除数 | `1` |
| 币种 | `USD` |

如果你填了 `https://example.com/v1` 作为站点地址，程序会自动避免拼成 `/v1/v1/usage`。

也可以使用 API Key Header 方式：

| 字段 | 推荐值 |
| --- | --- |
| 认证方式 | `API Key Header` |
| 认证 Header | `x-api-key` |
| 认证前缀 | 留空 |

## Telegram 告警

可以在后台右上角的设置按钮配置，也可以在第一次启动前通过 `.env` 初始化：

```dotenv
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:ABCDEF...
TELEGRAM_CHAT_ID=-1001234567890
```

告警规则：

1. 余额首次低于或等于站点阈值时发送一条消息。
2. 余额恢复到阈值以上后，重新进入可报警状态。
3. 同一站点连续第三次检查失败时发送一条失败告警。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ADMIN_USERNAME` | `admin` | Web 后台用户名 |
| `ADMIN_PASSWORD` | `change-me-now` | Web 后台密码，生产环境必须修改 |
| `DATA_DIR` | `/data` | SQLite 数据目录 |
| `DEFAULT_CHECK_INTERVAL_SECONDS` | `300` | 默认检查周期 |
| `HTTP_TIMEOUT_SECONDS` | `15` | 上游请求超时 |
| `TELEGRAM_ENABLED` | `false` | 是否启用 Telegram |
| `TELEGRAM_BOT_TOKEN` | 空 | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 空 | Telegram Chat ID |

## 项目结构

```text
ai-balance-monitor/
├── app/
│   ├── adapters/          # NewAPI / Sub2API 适配器
│   ├── services/          # 监控、Telegram、设置服务
│   ├── static/            # 管理后台 CSS/JS
│   ├── templates/         # 管理后台页面
│   ├── config.py
│   ├── db.py
│   ├── init_db.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 安全说明

- 不要提交 `.env`、`data/`、SQLite 数据库和任何真实站点令牌。
- 站点访问令牌会以明文保存在本机 SQLite 数据库中，请保护好服务器与后台密码。
- 生产环境建议将 `8080` 放在 HTTPS 反向代理之后，并限制后台访问来源。
- 如果你曾在聊天、日志或截图中暴露 GitHub/Gitee Token，请及时撤销并重新生成。

## License

MIT
