"""Agent Service FastAPI 入口(对内,只服务 Django)。

监听 127.0.0.1:8001,不对外暴露。启动方式(从项目根目录):
    uvicorn services.agent_service.backend.main:app --host 127.0.0.1 --port 8001

路径前置:FastAPI 路由不带 /api/v1 前缀,前缀由 Django 反代时保留。
"""
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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import agent as agent_routes
from .routes import health as health_routes
from .routes import workflow as workflow_routes

# 触发所有 agent 注册(agents/__init__.py 会调用 register_agent)
import agents  # noqa: F401,E402

app = FastAPI(title="AuditWeaver Agent Service", version="1.0")

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


@app.get("/")
async def root():
    return {"service": "agent_service", "status": "ok"}
