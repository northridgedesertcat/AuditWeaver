"""Agent Service FastAPI 入口(对内,只服务 Django)。

监听 127.0.0.1:8001,不对外暴露。启动方式(从项目根目录):
    uvicorn services.agent_service.backend.main:app --host 127.0.0.1 --port 8001

路径前置:FastAPI 路由不带 /api/v1 前缀,前缀由 Django 反代时保留。
"""
import asyncio
import os
import sys

# 把 agent_service 目录与项目根加入 sys.path,使 shared/ agents/ skills/
# registry/ common 都可被解析(本模块由 uvicorn 作为
# services.agent_service.backend.main 加载)。
_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_SERVICE_DIR = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_AGENT_SERVICE_DIR)
for _p in (_AGENT_SERVICE_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import agent as agent_routes
from .routes import health as health_routes
from .routes import threads as threads_routes
from .routes import workflow as workflow_routes

# 触发所有 agent 注册(agents/__init__.py 会调用 register_agent)
import agents  # noqa: F401,E402

# 启动期配置校验:配置错 fast fail,不拖到运行时(避免 400/404 才暴露)
from shared.config.validate import validate_runtime_config  # noqa: E402
from shared.config.settings import RAG_CONFIG  # noqa: E402
from shared.rag.case_sync import run_case_sync_forever  # noqa: E402

try:
    validate_runtime_config()
except Exception as e:
    # 打印后让异常向上传播,阻止 uvicorn 启动
    import sys
    print(f"[FATAL] Agent Service 配置校验失败: {e}", file=sys.stderr)
    raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期:启动 case 语料定时增量同步后台任务(P1-1),退出时取消。

    - AE_RAG_CASE_SYNC_ENABLED=false 关闭(仅手动建库)
    - 阻塞的 ES/embedding 调用在 run_case_sync_forever 内走 asyncio.to_thread
    - 单轮失败只记 error 日志,循环继续(水位未推进,下轮自动补齐)
    """
    sync_task = None
    if RAG_CONFIG.get("case_sync_enabled", True):
        interval = RAG_CONFIG.get("case_sync_interval", 300)
        sync_task = asyncio.create_task(run_case_sync_forever(interval=interval))
    yield
    if sync_task is not None:
        sync_task.cancel()
        try:
            await sync_task
        except (asyncio.CancelledError, Exception):  # noqa: B014
            pass


app = FastAPI(title="AuditWeaver Agent Service", version="1.0", lifespan=lifespan)

# FastAPI 仅对内服务 Django;开发期直接访问时放宽 CORS 以便联调
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_routes.router)
app.include_router(agent_routes.router)
app.include_router(workflow_routes.router)
app.include_router(threads_routes.router)


@app.get("/")
async def root():
    return {"service": "agent_service", "status": "ok"}
