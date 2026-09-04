"""工作流状态:线性流水线,非对话型(不继承 MessagesState)。

v1 不启用 checkpointer,无消息历史归约需求。
"""
from typing import TypedDict


class LogAnalysisState(TypedDict):
    """工作流状态。

    Attributes:
        log_data: 输入的结构化日志字段 {log_id, ip, path, method, status, user_agent, matched_type}
        retrieved_context: v2 预留,知识库检索结果;v1 为空串
        analysis: 输出的结构化分析结果(符合 AnalysisSchema)
    """
    log_data: dict
    retrieved_context: str
    analysis: dict
