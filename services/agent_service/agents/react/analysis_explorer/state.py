"""Analysis Explorer Agent 状态定义(对齐 §3.2 + §3.5)。

v2.1 升级:从 v1 的纯 MessagesState,扩展为结构化上下文管理(对齐 §3.5.1):
- current_plan: 当前调查计划(plan 节点生成,replan 时整体替换)
- investigation_summary: 已压缩的历史调查摘要(compact 产物,追加更新)
- evidence_pack: 结构化证据列表(工具调用收集,全程累积不丢)
- messages: 最近消息(滚动窗口,compact 时只取最近 N 条组装 Context)
- tool_history: 工具调用序列摘要(全程累积,仅摘要省 token)

辅助字段:
- decision_history: decision_llm 的决策记录(可追溯)
- compact_count: compact 已执行次数(防过度压缩,达 MAX_COMPACT_COUNT 降级)
- total_tokens_used: 累计 token 用量(预算制判断用)
- tool_rounds: 已执行工具调用轮数(预算制判断用)
- budget: 本轮 plan 决定的工具调用预算(简单 3/复杂 10)
- gate_triggered / gate_reasons: deterministic_gate 判断结果(便于条件路由)
- decision_result: decision_llm 最新决策(条件路由读 action)
- finish_reason: finish 时的理由(可追溯)
- final_report: 最终调查结论(finish 后由消费方写入,保留字段对齐 workflow 风格)

字段命名避免与 LangGraph 节点名冲突(参考 workflow 的 final_report 设计):
- 节点名:plan / agent / tools / deterministic_gate / decision_llm / compact
- state 字段用 current_plan / decision_result / compact_count 等,不与节点名同名
  (避免 LangGraph ValueError: node name conflicts with state key)

reducer 语义:
- messages: add_messages(MessagesState 自带,累加)
- tool_history / decision_history: operator.add 累加(全程保留历史)
- 其他字段:默认覆盖(每节点全量写回)
"""
from operator import add
from typing import Annotated

from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Agent 对话状态(对齐 §3.5 结构化上下文管理)。

    五字段结构化上下文(§3.5.1):
    - current_plan: 调查计划
    - investigation_summary: 压缩历史摘要
    - evidence_pack: 证据列表(零丢失)
    - tool_history: 工具调用摘要序列(全程累积)
    - messages: 最近消息(滚动窗口)

    辅助字段:
    - decision_history / compact_count / total_tokens_used / tool_rounds / budget
    - gate_triggered / gate_reasons / decision_result / finish_reason / final_report
    """

    # 五字段结构化上下文(§3.5.1)
    current_plan: dict
    investigation_summary: str
    evidence_pack: dict
    tool_history: Annotated[list[dict], add]  # 全程累积(仅摘要省 token)
    # 辅助字段
    decision_history: Annotated[list[dict], add]  # 决策记录,可追溯
    compact_count: int
    total_tokens_used: int
    tool_rounds: int
    budget: int
    # 门控 + 决策(每轮覆盖,便于条件路由读取)
    gate_triggered: bool
    gate_reasons: list[str]
    decision_result: dict
    finish_reason: str
    final_report: str
