"""Analysis Workflow Agent 注册。

启动时被 ``agents/workflow/__init__.py`` 触发,向 registry 注册 ``analysis_workflow``。
此 Agent 为线性工作流(非 ReAct 循环),单次执行无状态。
"""
from registry import register_agent
from .graph import build_graph


def _factory():
    # 每次编译新 graph,保证状态隔离(v1 无 checkpointer,每次独立执行)
    return build_graph()


register_agent("analysis_workflow", _factory)
