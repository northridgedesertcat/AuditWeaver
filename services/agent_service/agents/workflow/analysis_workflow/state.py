"""工作流状态:线性流水线,非对话型(不继承 MessagesState)。

v2.1 升级(对齐 §3.1):新增 evidence_pack / validate_result / enrich_count / report 字段,
支撑 retrieve → analyze → validate → enrich(↺≤2) → report 五节点流水线。

字段类型说明:
- evidence_pack: EvidencePack.model_dump() 的 dict 序列化形式(含 evidences 列表 +
  source_ids 属性的快照),避免 Pydantic 实例直接进 LangGraph state 的 reducer 问题。
  节点读取时按 dict 访问;需要 source_ids 时直接取 evidences 中的 source_id 字段。
- validate_result: {pass: bool, missing: list[str], reason: str}
  validate 节点输出,enrich 据此决定补检索词。
- enrich_count: enrich 已执行的次数,防死循环(≤ MAX_ENRICH_COUNT)。
- report: 最终报告文本(带 source_id 引用,无引用结论标记"推测")。

reducer 语义:
- 默认覆盖(LangGraph state 字段默认行为),evidence_pack / validate_result /
  enrich_count / report 都是"每节点全量写回",不需要 operator.add 累加。
  enrich_count 在 enrich_node 内显式 +1 写回,不依赖 reducer 累加。
"""
from typing import TypedDict


class LogAnalysisState(TypedDict):
    """工作流状态。

    Attributes:
        log_data: 输入的结构化日志字段 {log_id, ip, path, method, status, user_agent, matched_type}
        retrieved_context: v1 时代占位字段,v2.1 已被 evidence_pack 取代,保留向后兼容
        analysis: 输出的结构化分析结果(符合 AnalysisSchema)
        evidence_pack: RAG 检索得到的证据包(EvidencePack.model_dump() 形式),
            含 evidences 列表 + source_ids 快照,供 analyze/validate/report 引用溯源
        validate_result: 质量门控输出 {pass: bool, missing: list[str], reason: str}
        enrich_count: enrich 已执行次数,防死循环(≤ MAX_ENRICH_COUNT)
        final_report: 最终报告文本(带 source_id 引用,无引用结论标记"推测")
            注:字段名用 final_report 而非 report,避免与 LangGraph 节点名 "report" 冲突
            (LangGraph 不允许节点名与 state key 同名)
    """
    log_data: dict
    retrieved_context: str
    analysis: dict
    evidence_pack: dict
    validate_result: dict
    enrich_count: int
    final_report: str
