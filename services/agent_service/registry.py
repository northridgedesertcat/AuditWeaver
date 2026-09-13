"""Agent 注册表(agent_type -> graph 工厂)。

FastAPI 启动时遍历 ``agents/`` 下所有子包并触发注册;路由层按
``agent_type`` 路径参数从注册表取出对应的 graph 实例。新增 Agent
不改 FastAPI 路由代码,只动 ``agents/`` 目录。
"""
from typing import Callable, Dict

from langgraph.graph.state import CompiledStateGraph

# 每个 agent 注册一个工厂函数,返回编译好的 graph
AgentFactory = Callable[[], CompiledStateGraph]

_REGISTRY: Dict[str, AgentFactory] = {}


def register_agent(agent_type: str, factory: AgentFactory) -> None:
    """供 ``agents/<name>/__init__.py`` 调用,启动时自动注册。"""
    _REGISTRY[agent_type] = factory


def get_agent(agent_type: str) -> CompiledStateGraph:
    """按 agent_type 取出一个新编译的 graph 实例。

    每次 build 一次新 graph,保证 checkpointer / 状态隔离。
    未知 agent_type 抛 ValueError(由 FastAPI 层转 404)。
    """
    factory = _REGISTRY.get(agent_type)
    if factory is None:
        raise ValueError(f"Unknown agent_type: {agent_type}")
    return factory()


def list_agent_types() -> list[str]:
    return list(_REGISTRY.keys())
