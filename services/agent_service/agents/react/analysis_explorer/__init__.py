"""Analysis Explorer Agent 注册。

启动时被 ``agents/__init__.py`` 触发,向 registry 注册 ``analysis_explorer``。
新增 Agent 时仿照此结构新建子包,并在 ``agents/__init__.py`` 加一行 import。
"""
from registry import register_agent
from .graph import build_graph


def _factory():
    # 每次 build 一次新 graph,保证 checkpointer / 状态隔离
    return build_graph()


register_agent("analysis_explorer", _factory)
