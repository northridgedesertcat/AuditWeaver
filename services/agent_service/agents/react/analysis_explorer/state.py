"""Analysis Explorer Agent 状态定义。

沿用 LangGraph 的 ``MessagesState``(自带 ``messages`` 与 ``add_messages`` 归约),
留出子类以便后续扩展(如加入中间结构化字段)。
"""
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """对话状态:消息历史 + (预留)自定义字段。"""
    pass
