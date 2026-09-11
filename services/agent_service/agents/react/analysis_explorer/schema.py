"""结构化输出 Schema(对齐 §3.2)。

Schemas:
- PlanSchema: plan 节点输出(假设列表 + 验证步骤 + 预期证据 + 预算)
- DecisionSchema: decision_llm 节点输出(四选一:continue/replan/compact/finish)
- CompactSummarySchema: compact 节点输出(压缩摘要 + 保留证据 ID + 丢弃数)

字段均设默认值:本地小模型(如 qwen2.5:7b)tool calling 不稳,
漏字段时降级而非校验崩溃,与 workflow schema 风格一致。
"""
from pydantic import BaseModel, Field


class PlanSchema(BaseModel):
    """plan 节点结构化输出:调查计划(Plan-and-Solve 范式,对齐 §3.2.1)。

    给后续 ReAct 一个明确任务指导,避免裸 ReAct"原地打转"的缺陷。

    Attributes:
        hypotheses: 待验证的假设列表,每个假设是一个明确判断,例如
            ['IP 1.1.1.1 在进行端口扫描', '该 IP 关联 SQLi 攻击']
        steps: 验证步骤列表,每步对应一个工具调用意图,例如
            ['查 1.1.1.1 的 nginx 日志(QueryIPLogs)',
             '查该 IP 的安全事件(QuerySecurityEvents)']
        expected_evidence: 预期需要的证据类型列表,供 deterministic_gate
            判断"证据不足"触发条件,例如 ['IP 的访问记录', '攻击类型匹配']
        budget: 本轮调查的工具调用上限(简单问题 3,复杂调查 10)
    """

    hypotheses: list[str] = Field(
        default_factory=list,
        description="待验证的假设列表",
    )
    steps: list[str] = Field(
        default_factory=list,
        description="验证步骤列表,每步对应一个工具调用意图",
    )
    expected_evidence: list[str] = Field(
        default_factory=list,
        description="预期需要的证据类型,用于 deterministic_gate 判断证据是否充足",
    )
    budget: int = Field(
        default=5,
        description="本轮调查的工具调用预算(简单 3 / 复杂 10)",
    )


class DecisionSchema(BaseModel):
    """decision_llm 节点结构化输出:四选一决策(对齐 §3.2.3)。

    仅在 deterministic_gate 命中触发条件时调用(省 LLM 调用)。
    用 light 模型省钱:语义判断但不需强推理。

    Attributes:
        action: 决策动作,continue(继续)/ replan(重规划)/
            compact(压缩上下文)/ finish(结束)
        reason: 决策理由(可解释、可追溯)
        next_step: 下一步建议,例如 '查 IP 1.2.3.4 的日志' 或
            '总结失败路径并重新规划' 或 '输出最终结论'
    """

    action: str = Field(
        default="continue",
        description="决策动作:continue / replan / compact / finish 之一",
    )
    reason: str = Field(
        default="",
        description="决策理由(可解释、可追溯)",
    )
    next_step: str = Field(
        default="",
        description="下一步建议",
    )


class CompactSummarySchema(BaseModel):
    """compact 节点结构化输出:压缩摘要(对齐 §3.5.3)。

    用 light 模型:摘要要忠实,温度 0.0。

    Attributes:
        summary: 压缩后的调查摘要(追加到 investigation_summary)
        preserved_evidence_ids: 本轮压缩涉及的核心证据 source_id 列表(便于审计)
        dropped_count: 本次压缩丢弃的消息数量
    """

    summary: str = Field(
        default="",
        description="压缩后的调查摘要,追加到 investigation_summary",
    )
    preserved_evidence_ids: list[str] = Field(
        default_factory=list,
        description="本轮压缩涉及的核心证据 source_id 列表(便于审计)",
    )
    dropped_count: int = Field(
        default=0,
        description="本次压缩丢弃的消息数量",
    )
