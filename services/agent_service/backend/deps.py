"""依赖注入:从 registry 取 graph / 列出 agent_type。

FastAPI 路由按 ``agent_type`` 路径参数分发,新增 Agent 不改路由。
"""
from registry import get_agent, list_agent_types

__all__ = ["get_graph", "list_agent_types"]


def get_graph(agent_type: str):
    """按 agent_type 取出一个新编译的 graph 实例。

    未知 agent_type 抛 ValueError(由路由层转 404)。
    """
    return get_agent(agent_type)
