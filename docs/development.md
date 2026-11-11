# 开发与服务管理

## 环境约定

- Python 最低 3.12，推荐 3.13；Node.js 使用 22.13+ 的 22 LTS 系列或 24+，推荐 22 LTS；npm 10+。这是当前检查工具依赖的版本约束，高于 Next.js 本身的最低要求。
- Python 依赖安装到项目 `.venv`。`dev.py` 和 Windows 双击脚本会优先使用它，不修改全局 Python。
- 运行依赖在 `requirements.txt`；孤立森林训练、评估和推理的附加依赖在 `requirements-model.txt`。
- Python 顶层依赖有版本约束，但目前尚未形成跨平台的完整传递依赖锁；不承诺所有间接依赖完全一致。
- 前端只维护 npm 的 `package-lock.json`。日常安装和 CI 使用 `npm ci`；增加依赖时使用 `npm install` 并提交锁文件。
- 配置来源为根目录 `.env`，已有进程环境变量优先。不要提交真实密钥或把 `.env` 写进日志。

首次准备按 README 创建虚拟环境并安装依赖，再复制 `.env.example` 为 `.env`。
生成 Django 密钥可运行 `python -c "import secrets; print(secrets.token_urlsafe(48))"`。
Redis 密码、两个 Redis URL 和模型服务配置需要自行填写，不在模板中保存真实凭据。

## 统一入口

在项目根目录运行：

```bash
python dev.py doctor
python dev.py start
python dev.py status
python dev.py logs agent_service --tail 100
python dev.py logs django frontend --follow
python dev.py stop
```

服务 ID 为 `rule_engine`、`agent_service`、`agent`、`django`、`frontend`。
服务清单只维护在 `scripts/config.py`。`start.py`、`start.bat`、`stop.bat` 都是兼容封装。
Linux / WSL 使用相同的 Python 入口，无需图形终端。

进程状态写入 `.run/`，输出追加至 `logs/services/<service>.log`，两者都不进入 Git。
不要在服务运行时删除 `.run`，否则管理入口会失去进程身份记录。
旧脚本或编辑器启动的进程不会被自动接管；首次切换前请在原窗口或编辑器中停止旧进程。
管理入口不会按端口或窗口标题批量终止程序。

## 开发方式

整套本机联调：

```bash
python dev.py start --tools
```

基础服务运行在 Docker，业务服务运行在本机。Kibana 默认不启动，`--tools` 启用它。
当前尚未提供全部业务服务容器化的运行方式。

编辑器调试 Django，其他服务交给入口管理：

```bash
python dev.py start rule_engine agent_service agent frontend
```

仅运行前端，不启动基础服务、不要求后端密钥：

```bash
python dev.py start frontend --no-docker
python dev.py stop frontend
```

自管基础服务时，对启动、停止和状态命令使用 `--no-docker`。
指定服务的 `stop` 仅停止指定业务进程；不指定服务的 `stop` 默认同时停止 Compose 容器。
停止使用 `compose stop`，保留容器、网络及数据卷，不执行 `down -v`。
Compose 保留原容器名和持久卷名；多个仓库副本不能同时使用这些同名基础服务。

## 启动与失败处理

启动顺序为：基础服务健康检查、所选业务的依赖检查和初始化、数据库迁移、业务进程。
因此数据库未就绪或迁移失败时，不会启动分析进程。
Agent Service 在分析进程前启动，避免 LangGraph 分析后端尚未监听时就开始消费。

- HTTP 服务启动时检查健康接口；进程退出或等待超时都返回非零退出码。
- 两个 Kafka 工作进程暂时只有启动存活检查，不能代替消息实际消费、报告落库的端到端验证。
- 已受管理的进程不会重复启动；未受管理的程序占用目标端口时直接报错。
- 业务启动失败或被中断时，只停止本次新启动的业务进程，保留原本已运行的进程。
- Docker 容器和已完成的迁移、索引、Topic 初始化不会因后续失败自动撤销；日志会保留供排查。
- 对已经运行的服务再次启动不会重复初始化。启动新的业务服务时会运行其依赖的初始化和迁移；Kafka Connect 当前初始化脚本仍会重建连接器，生产环境不应使用这个开发入口。
- `status` 会重新检查进程和 HTTP 接口；任一所选服务停止或不健康时返回非零退出码。
- Django 的托管启动关闭自动重载，编辑 Python 后重启该服务，或在编辑器中自行启动带重载的 Django。

首次创建 Root Admin 仍为显式交互操作，不在启动脚本中自动创建账号：

```bash
python services/website/backend/v1/manage.py create_root_admin
```

## 地址与端口

- `DJANGO_PORT`、`FRONTEND_PORT`、`AE_BACKEND_HOST` 和 `AE_BACKEND_PORT` 决定本机监听地址。
- Next.js 服务端反代使用 `DJANGO_API_BASE`；留空时自动使用 `http://localhost:<DJANGO_PORT>`。
- 修改 Django 端口后，如果显式设置过 `NEXT_PUBLIC_API_BASE`，也要同步调整；Django 到 Agent 的显式地址同理。
- 容器化前端时可把 `DJANGO_API_BASE` 改为 `http://django:8000`，但前提是确实已建立该容器服务。
- Next.js 仍保留尾斜杠和关闭压缩的配置，避免影响现有 Django 路由与 SSE 流式响应。

## 检查

```bash
python dev.py check
python dev.py check --python-only
python dev.py check --build
```

统一检查包括依赖一致性、管理入口测试、规则引擎、重试、熔断、Agent 重试与降级、Django 配置检查，以及前端测试、类型检查和 ESLint。
`--build` 额外执行前端生产构建。检查不启动业务服务、不迁移真实数据库，也不调用 LLM。
Django 配置检查在未设置密钥时使用仅供检查的占位值，不写入 `.env`。

前端构建不再忽略 TypeScript 错误。ESLint 保留 Hooks 顺序、依赖与 Next.js 规则；暂未启用 `react-hooks/set-state-in-effect`，因为现有异步加载器在请求前同步更新 loading/error，相关状态管理重构留待单独处理。
现有 Agent Service 与 Django 数据库集成测试尚未全部纳入这个离线入口，完整消息链路仍需服务就绪后单独验证。

GitHub Actions 对 Windows 和 Ubuntu 运行相同检查及构建。这不是完整 Docker 联调，也不会调用外部模型。

## WSL2 后续迁移

本次没有迁移代码、创建 Linux 环境或改动 Docker Desktop 设置。
后续可将代码放到 WSL Linux 文件系统（例如 `~/projects/AuditWeaver`），重新创建 `.venv` 和安装 Node/npm 依赖，不复用 Windows 的 `.venv` 或 `node_modules`。
先验证 `doctor` 和 `check --build`，再验证 Docker 集成和完整消息链路。
