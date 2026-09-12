"""Analysis Explorer Agent 节点实现(对齐 §3.2 + §3.5)。

v2.1 升级:从 v1 的二节点(agent ⇄ tools)扩展为六节点:

    START → plan → agent ⇄ tools → deterministic_gate →
            (未命中)→ agent(省一次 LLM 调用)
            (命中触发条件)→ decision_llm → continue→agent /
                                         replan→plan /
                                         compact→compact→agent /
                                         finish→END

节点职责:
- plan_node: LLM 生成结构化调查计划(Plan-and-Solve),给后续 ReAct 明确任务指导
- agent_node(改造 v1): 注入结构化上下文(system prompt + recent messages),
  保留 v1 的 bind_tools ReAct 内核
- tools_node(改造 v1): 用 get_wrapped_mcp_tools 取带 spec 的工具,
  从 ToolResult 提取 source_ids + evidence 累积到 evidence_pack
- deterministic_gate_node: 纯代码规则,零 LLM 调用,命中 7 条触发条件之一才进 decision_llm
- decision_llm_node: light 模型四选一决策(continue/replan/compact/finish)
- compact_node: 结构化上下文压缩,不重写 message history(对齐 §3.5)

LLM 调用契约:
- plan: get_llm(role='analysis') 强模型 + PlanSchema
- agent: get_llm(role='analysis') 强模型 + bind_tools(ReAct 内核)
- decision_llm: get_llm(role='light') 弱模型 + DecisionSchema(语义判断不需强推理)
- compact: get_llm(role='light') 弱模型 + CompactSummarySchema(摘要要忠实)

State 字段读写(对齐 state.py):
- current_plan: plan 写,agent/deterministic_gate/decision_llm 读
- investigation_summary: compact 写(追加),agent/decision_llm 读
- evidence_pack: tools 写(累积),agent/deterministic_gate/decision_llm 读
- tool_history: tools 写(累加),agent/deterministic_gate/decision_llm/compact 读
- decision_history: decision_llm 写(累加),可追溯
- compact_count: compact 写(+1),agent 读(决定是否只取 recent N 条)
- tool_rounds: tools 写(+1),deterministic_gate 读(预算判断)
- budget: plan 写,deterministic_gate 读(预算判断)
- gate_triggered / gate_reasons: deterministic_gate 写,graph 条件边读
- decision_result: decision_llm 写,graph 条件边读
- finish_reason: decision_llm 写(finish 时),可追溯
"""
import asyncio
import json
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.prebuilt import ToolNode

from shared.llm.factory import get_llm
from shared.llm.retry import invoke_structured_with_retry
from shared.mcp_client import get_wrapped_mcp_tools
from .config.settings import (
    COMPACT_TEMPERATURE,
    DECISION_TEMPERATURE,
    DEFAULT_BUDGET_COMPLEX,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    MAX_COMPACT_COUNT,
    PLAN_TEMPERATURE,
    RECENT_MESSAGES_N,
    TEMPERATURE,
)
# 确定性门控触发条件阈值
from .config.settings import (
    CONSECUTIVE_FAILURE_THRESHOLD,
    DUPLICATE_ROUNDS_THRESHOLD,
    EXPECTED_EVIDENCE_MIN,
    TOKEN_BUDGET_THRESHOLD,
)
from .prompts import (
    render_compact_prompt,
    render_decision_prompt,
    render_plan_prompt,
    render_system_prompt,
)
from .schema import CompactSummarySchema, DecisionSchema, PlanSchema

logger = logging.getLogger(__name__)

# ============ LLM 懒加载缓存(进程内单例,避免每次节点调用重新初始化)============

_llm_plan: BaseChatModel | None = None           # plan 节点(analysis + PlanSchema)
_llm_with_tools: BaseChatModel | None = None      # agent 节点(analysis + bind_tools)
_tools_node: ToolNode | None = None               # tools 节点(共用,agent/tools 都用)
_llm_decision: BaseChatModel | None = None        # decision_llm 节点(light + DecisionSchema)
_llm_compact: BaseChatModel | None = None          # compact 节点(light + CompactSummarySchema)
_init_lock = asyncio.Lock()


async def _ensure_agent_components() -> tuple[BaseChatModel, ToolNode | None]:
    """懒加载 agent + tools 节点共用的 LLM(analysis + bind_tools)与 ToolNode。

    返回 (llm_with_tools, tool_node):
    - llm_with_tools: analysis 模型 bind_tools 后的 Runnable,agent_node 用
    - tool_node: ToolNode(包装后的 MCP 工具),tools_node 用;无工具时为 None

    用 get_wrapped_mcp_tools(caller='analysis_explorer')(对齐 §3.6,带 ToolResult/
    timeout/retry/审计),caller 标识写入审计日志便于追溯。
    """
    global _llm_with_tools, _tools_node
    if _llm_with_tools is not None:
        return _llm_with_tools, _tools_node
    async with _init_lock:
        if _llm_with_tools is not None:
            return _llm_with_tools, _tools_node
        llm = get_llm(
            role="analysis",
            temperature=TEMPERATURE,
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
        )
        tools = await get_wrapped_mcp_tools(caller="analysis_explorer")
        if tools:
            _llm_with_tools = llm.bind_tools(tools)
            _tools_node = ToolNode(tools)
        else:
            # 没有可用工具时退化为直接对话(对齐 v1 行为)
            _llm_with_tools = llm
            _tools_node = None
        return _llm_with_tools, _tools_node


async def _ensure_plan_llm() -> BaseChatModel:
    """懒加载 plan 节点的结构化输出 LLM(analysis + PlanSchema)。"""
    global _llm_plan
    if _llm_plan is not None:
        return _llm_plan
    async with _init_lock:
        if _llm_plan is not None:
            return _llm_plan
        llm = get_llm(
            role="analysis",
            temperature=PLAN_TEMPERATURE,
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            streaming=False,
        )
        # method="function_calling":schema 走 tools 参数由模型 tool_calls 回填,
        # 不用 response_format=json_schema(DeepSeek 实测 400:
        # "This response_format type is unavailable now";function calling 全厂商支持)
        _llm_plan = llm.with_structured_output(PlanSchema, method="function_calling")
        return _llm_plan


async def _ensure_decision_llm() -> BaseChatModel:
    """懒加载 decision_llm 节点的结构化输出 LLM(light + DecisionSchema)。

    用 light 模型省钱(语义判断不需强推理),温度 0.1(门控保守)。
    """
    global _llm_decision
    if _llm_decision is not None:
        return _llm_decision
    async with _init_lock:
        if _llm_decision is not None:
            return _llm_decision
        llm = get_llm(
            role="light",
            temperature=DECISION_TEMPERATURE,
            streaming=False,
        )
        _llm_decision = llm.with_structured_output(DecisionSchema, method="function_calling")
        return _llm_decision


async def _ensure_compact_llm() -> BaseChatModel:
    """懒加载 compact 节点的结构化输出 LLM(light + CompactSummarySchema)。

    用 light 模型(摘要要忠实,不需强推理),温度 0.0(摘要不能创造内容)。
    """
    global _llm_compact
    if _llm_compact is not None:
        return _llm_compact
    async with _init_lock:
        if _llm_compact is not None:
            return _llm_compact
        llm = get_llm(
            role="light",
            temperature=COMPACT_TEMPERATURE,
            streaming=False,
        )
        _llm_compact = llm.with_structured_output(
            CompactSummarySchema, method="function_calling"
        )
        return _llm_compact


# ============ 辅助函数:从 state / ToolResult 提取信息 ============


def _extract_user_query(state: dict) -> str:
    """从 state.messages 找最后一条 human 消息的 content,作为用户原始问题。

    plan 节点用此构造 plan prompt。LangGraph 的 HumanMessage.type == "human"。
    兜底:找不到 human 消息时返回空串(让 plan prompt 的占位文本兜底)。
    """
    messages = state.get("messages") or []
    for m in reversed(messages):
        if getattr(m, "type", None) == "human":
            content = getattr(m, "content", "")
            if isinstance(content, list):
                # HumanMessage content 可能是 list(多模态),取第一段文本
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return str(part.get("content", ""))
                    if isinstance(part, str):
                        return part
            return str(content) if content else ""
    return ""


def _parse_tool_result(content: Any) -> dict | None:
    """从 ToolMessage.content 解析 ToolResult JSON。

    wrapper._run_with_spec 返回 ToolResult.to_json() 字符串,
    ToolMessage.content 即此字符串。解析失败返回 None(让调用方降级处理)。
    """
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def _summarize_args(messages: list[BaseMessage]) -> str:
    """从最近 AIMessage 的 tool_calls 提取入参摘要。

    tools_node 执行前,agent_node 刚发了 AIMessage(含 tool_calls)。
    这里找最近一条 AIMessage,取其 tool_calls 的入参,拼成 "k=v, k=v" 摘要。
    找不到时返回空串。
    """
    for m in reversed(messages):
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            parts = []
            for tc in m.tool_calls:
                args = tc.get("args") or {}
                if isinstance(args, dict):
                    parts.append(
                        ", ".join(f"{k}={v}" for k, v in args.items())
                    )
            return " | ".join(parts) if parts else ""
    return ""


def _summarize_result(tool_result: dict | None) -> str:
    """构造工具调用结果摘要(写进 tool_history,供 LLM 看历史不读原始 JSON)。

    - 成功:从 data 里数 logs/events/reports 列表长度,拼 "ok(N records)"
    - 失败:"FAIL: <error>"
    - 解析失败:"(无法解析结果)"
    """
    if tool_result is None:
        return "(无法解析结果)"
    ok = tool_result.get("ok", False)
    if ok:
        data = tool_result.get("data")
        # 常见 data 形态:{"logs": [...], "events": [...], "reports": [...]}
        count = 0
        if isinstance(data, dict):
            for k in ("logs", "events", "reports", "items", "results"):
                v = data.get(k)
                if isinstance(v, list):
                    count += len(v)
        elif isinstance(data, list):
            count = len(data)
        return f"ok({count} records)" if count > 0 else "ok"
    error = tool_result.get("error") or "unknown error"
    return f"FAIL: {error}"


def _describe_tool_record(record: dict, source_type: str) -> str:
    """把单条工具返回记录(dict)拼成自然语言 content(写进 evidence.content)。

    扫描常见字段(ip/path/method/status/attack_type/risk_level/timestamp),
    拼成 "IP 1.1.1.1 GET /admin 401 attack_type=SQLi risk_level=High" 形式。
    找不到任何字段时兜底用 json.dumps(截断 200 字)。
    """
    if not isinstance(record, dict):
        return str(record)[:200]

    parts = []
    field_map = [
        ("ip", "IP"), ("client_ip", "IP"),
        ("method", ""), ("path", ""), ("url", ""),
        ("status", "status"), ("status_code", "status"),
        ("attack_type", "attack"), ("matched_type", "matched"),
        ("risk_level", "risk"), ("severity", "severity"),
        ("timestamp", "ts"), ("time", "ts"),
    ]
    for key, label in field_map:
        v = record.get(key)
        if v:
            prefix = f"{label}=" if label else ""
            parts.append(f"{prefix}{v}")

    if parts:
        return " ".join(parts)
    # 兜底:json 截断
    try:
        return json.dumps(record, ensure_ascii=False)[:200]
    except (TypeError, ValueError):
        return str(record)[:200]


def _extract_evidences_from_tool_result(
    tool_result: dict | None,
    tool_name: str,
) -> list[dict]:
    """从 ToolResult.data 提取 evidence 列表(写进 evidence_pack.evidences)。

    扫描 data 里的 logs / events / reports 列表,每条记录转成一条 evidence:
    - content: 自然语言描述(用 _describe_tool_record)
    - source_id: 从 record 里取 event_id / source_id / _id / id(对齐 wrapper._SOURCE_ID_FIELDS)
    - score: 0.0(Agent 收集的证据不带检索分数,与 RAG evidence 区分)
    - source_type: "tool_<tool_name>"(标记来源是哪个工具)
    - raw: 原始记录(供 deterministic_gate 判断"证据冲突"用,如读 risk_level)

    截断到前 20 条防 evidence_pack 膨胀(对齐设计 §3.5)。
    """
    if not tool_result or not tool_result.get("ok"):
        return []

    data = tool_result.get("data")
    records: list[dict] = []
    if isinstance(data, dict):
        for k in ("logs", "events", "reports", "items", "results"):
            v = data.get(k)
            if isinstance(v, list):
                records.extend(r for r in v if isinstance(r, dict))
    elif isinstance(data, list):
        records.extend(r for r in data if isinstance(r, dict))

    # 截断到前 20 条
    records = records[:20]

    evidences = []
    source_type = f"tool_{tool_name}"
    for record in records:
        sid = ""
        for id_key in ("event_id", "source_id", "_id", "id"):
            v = record.get(id_key)
            if v:
                sid = str(v)
                break
        evidences.append({
            "content": _describe_tool_record(record, source_type),
            "source_id": sid,
            "score": 0.0,
            "source_type": source_type,
            "raw": record,
        })
    return evidences


def _merge_evidences_into_pack(
    old_pack: dict | None,
    new_evidences: list[dict],
) -> dict:
    """把新 evidence 合并进 evidence_pack(去重 by source_id)。

    去重策略(对齐 workflow enrich_node):
    - 有 source_id 的:by source_id 去重
    - 无 source_id 的:用 content[:50] 兜底去重(避免空 sid 的重复记录)

    返回合并后的 evidence_pack(dict 形态,对齐 EvidencePack.model_dump())。
    """
    if not isinstance(old_pack, dict):
        old_pack = {
            "query": "", "evidences": [], "fused": False, "sources": [],
        }
    old_evidences = old_pack.get("evidences") or []

    seen_ids: set[str] = set()
    merged: list[dict] = []
    for ev in old_evidences + new_evidences:
        sid = ev.get("source_id") or ev.get("content", "")[:50]
        if not sid:
            sid = f"auto_{id(ev)}"  # 极端兜底:用对象 id 保证不重复
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        merged.append(ev)

    return {
        "query": old_pack.get("query", ""),
        "evidences": merged,
        "fused": old_pack.get("fused", False),
        "sources": old_pack.get("sources") or [],
    }


# ============ plan 节点(LLM 生成结构化调查计划)============


async def plan_node(state: dict) -> dict:
    """plan 节点:根据用户问题生成结构化调查计划(Plan-and-Solve 范式)。

    设计要点(对齐 §3.2.1):
    - 给后续 ReAct 一个明确任务指导,避免裸 ReAct"原地打转"的缺陷
    - 输出 PlanSchema{hypotheses, steps, expected_evidence, budget}
    - budget 决定本轮调查的工具调用上限(简单 3 / 复杂 10,预算制对齐 §3.2.2)
    - replan 时会重新进入此节点,整体替换 current_plan + 重置 tool_rounds

    State 写入:
    - current_plan: PlanSchema.model_dump()
    - budget: 从 plan 取(兜底 DEFAULT_BUDGET_COMPLEX,防 LLM 漏字段)
    - tool_rounds: 重置为 0(replan 后重新计数)
    """
    llm_plan = await _ensure_plan_llm()
    user_query = _extract_user_query(state)
    messages = render_plan_prompt(user_query)
    result = await invoke_structured_with_retry(
        llm_plan, messages, PlanSchema, role="analysis",
    )
    plan_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    budget = plan_dict.get("budget") or DEFAULT_BUDGET_COMPLEX
    logger.info(
        "[agent.plan] hypotheses=%d steps=%d expected_evidence=%d budget=%d",
        len(plan_dict.get("hypotheses") or []),
        len(plan_dict.get("steps") or []),
        len(plan_dict.get("expected_evidence") or []),
        budget,
    )
    return {
        "current_plan": plan_dict,
        "budget": budget,
        "tool_rounds": 0,  # replan 后重置
    }


# ============ agent 节点(改造 v1:注入结构化上下文)============


async def agent_node(state: dict) -> dict:
    """LLM 决策节点:直接回答 or 发起 tool_calls。

    v2.1 改造(对齐 §3.5):
    - 用 render_system_prompt 注入结构化上下文(plan/investigation_summary/
      evidence_pack/tool_history),LLM 每轮看到全局调查状态
    - compact_count > 0 时只取 messages[-RECENT_MESSAGES_N:](对齐 §3.5.3
      "保留最近 N 轮"),靠结构化字段(summary+evidence)承载历史,省 token
    - compact_count == 0 时用全部 messages(首轮或未压缩,完整历史)
    - 保留 v1 的 bind_tools ReAct 内核(LLM 自主决定调工具还是直接回答)

    返回 {"messages": [response]}(对齐 v1,LanguagesGraph messages reducer 累加)。
    """
    llm_with_tools, _ = await _ensure_agent_components()
    # 注入结构化上下文(每轮都前置,LLM 始终看到调查状态)
    system_text = render_system_prompt(
        state.get("current_plan"),
        state.get("investigation_summary", ""),
        state.get("evidence_pack"),
        state.get("tool_history") or [],
    )
    messages = list(state.get("messages") or [])
    # compact 后只取最近 N 条(对齐 §3.5.3,省 token)
    compact_count = state.get("compact_count", 0) or 0
    if compact_count > 0 and len(messages) > RECENT_MESSAGES_N:
        recent = messages[-RECENT_MESSAGES_N:]
    else:
        recent = messages
    full_messages = [SystemMessage(content=system_text)] + recent
    response = await llm_with_tools.ainvoke(full_messages)
    return {"messages": [response]}


# ============ tools 节点(改造 v1:提取 evidence + tool_history)============


async def tools_node(state: dict) -> dict:
    """工具执行节点:执行 tool_calls + 从 ToolResult 提取 evidence 累积到 evidence_pack。

    v2.1 改造(对齐 §3.5 + §3.6):
    - 用 _ensure_agent_components 返回的 ToolNode(包装后的 MCP 工具,
      带 ToolResult/timeout/retry/审计)
    - 从 ToolMessage.content 解析 ToolResult JSON(对齐 wrapper._run_with_spec 返回)
    - 提取 source_ids / ok / data / error / duration_ms,构造 tool_history 条目
    - 从 data.logs/events/reports 提取 evidence,合并到 evidence_pack(去重 by source_id)
    - tool_rounds +1(预算制,deterministic_gate 据此判断预算临界)

    State 写入:
    - messages: ToolNode 返回的 ToolMessage 列表(累加)
    - evidence_pack: 合并后的 evidence_pack(覆盖,因为已含旧 evidence)
    - tool_history: 本轮工具调用摘要(累加,Annotated[list, add])
    - tool_rounds: +1(覆盖,非累加)
    """
    _, tool_node = await _ensure_agent_components()
    if tool_node is None:
        # 无工具可用(对齐 v1 降级),不更新 evidence/tool_history
        return {"messages": []}

    # 执行工具(ToolNode 会读 state.messages 里的 AIMessage.tool_calls)
    result = await tool_node.ainvoke(state)
    new_messages = result.get("messages", []) if isinstance(result, dict) else []

    # 从 ToolMessage 解析 ToolResult,提取 evidence + 构造 tool_history
    old_messages = state.get("messages") or []
    args_summary = _summarize_args(old_messages)
    old_pack = state.get("evidence_pack")
    all_new_evidences: list[dict] = []
    history_entries: list[dict] = []

    for msg in new_messages:
        tool_name = getattr(msg, "name", "") or "unknown"
        tool_result = _parse_tool_result(getattr(msg, "content", ""))
        ok = tool_result.get("ok", False) if tool_result else False
        source_ids = tool_result.get("source_ids") or [] if tool_result else []
        duration_ms = tool_result.get("duration_ms", 0.0) if tool_result else 0.0
        result_summary = _summarize_result(tool_result)
        # 构造 tool_history 条目(写进 state.tool_history,供 LLM 看历史不读原始 JSON)
        history_entries.append({
            "tool_name": tool_name,
            "args_summary": args_summary,
            "result_summary": result_summary,
            "source_ids": source_ids,
            "ok": ok,
            "duration_ms": duration_ms,
        })
        # 从 ToolResult.data 提取 evidence,累积到 all_new_evidences
        evidences = _extract_evidences_from_tool_result(tool_result, tool_name)
        all_new_evidences.extend(evidences)

    # 合并 evidence 到 evidence_pack(去重 by source_id)
    updated_pack = _merge_evidences_into_pack(old_pack, all_new_evidences)
    tool_rounds = (state.get("tool_rounds", 0) or 0) + 1

    logger.info(
        "[agent.tools] tool_rounds=%d new_evidences=%d total_evidences=%d",
        tool_rounds, len(all_new_evidences),
        len(updated_pack.get("evidences") or []),
    )

    return {
        "messages": new_messages,
        "evidence_pack": updated_pack,
        "tool_history": history_entries,
        "tool_rounds": tool_rounds,
    }


# ============ deterministic_gate 节点(纯代码规则,零 LLM 调用)============


def _evaluate_gate_conditions(state: dict) -> tuple[bool, list[str]]:
    """确定性门控:纯代码规则判断是否需要进入 decision_llm。

    对齐 §3.2.3 七条触发条件:
    1. 工具失败 / 连续失败:最近一轮 ok=False 或连续失败 ≥ CONSECUTIVE_FAILURE_THRESHOLD
    2. 证据不足:evidence_pack 条数 < EXPECTED_EVIDENCE_MIN
    3. 证据冲突:多条 evidence 的 raw.risk_level 不一致
    4. 预算临界:剩余轮数 ≤ max(1, int(budget*0.2)) 或 total_tokens ≥ TOKEN_BUDGET_THRESHOLD
    5. 重复 / 停滞:最近 DUPLICATE_ROUNDS_THRESHOLD 轮 args_summary 相同,或最近一轮无新 source_ids
    6. 可能完成:len(evidences) ≥ len(hypotheses)(证据覆盖所有假设)
    7. 需要改变方向:同时有"冲突"和"失败"(组合判断)

    返回 (triggered: bool, reasons: list[str])。
    triggered = len(reasons) > 0(命中任一条件即进 decision_llm)。
    """
    reasons: list[str] = []

    # --- 读取 state ---
    tool_history = state.get("tool_history") or []
    evidence_pack = state.get("evidence_pack") or {}
    evidences = evidence_pack.get("evidences") or []
    current_plan = state.get("current_plan") or {}
    hypotheses = current_plan.get("hypotheses") or []
    expected_evidence = current_plan.get("expected_evidence") or []
    budget = state.get("budget", 0) or 0
    tool_rounds = state.get("tool_rounds", 0) or 0
    total_tokens = state.get("total_tokens_used", 0) or 0

    # --- 条件 1:工具失败 / 连续失败 ---
    if tool_history:
        # 最近一轮失败
        last = tool_history[-1]
        if not last.get("ok", True):
            reasons.append("最近一轮工具调用失败")
        # 连续失败达阈值
        consecutive_fail = 0
        for h in reversed(tool_history):
            if not h.get("ok", True):
                consecutive_fail += 1
            else:
                break
        if consecutive_fail >= CONSECUTIVE_FAILURE_THRESHOLD:
            reasons.append(
                f"连续 {consecutive_fail} 轮工具失败(达阈值 {CONSECUTIVE_FAILURE_THRESHOLD})"
            )

    # --- 条件 2:证据不足 ---
    # 用 expected_evidence 的长度作为预期下限(若 plan 给了),否则用全局 EXPECTED_EVIDENCE_MIN
    expected_min = len(expected_evidence) if expected_evidence else EXPECTED_EVIDENCE_MIN
    if len(evidences) < expected_min:
        reasons.append(
            f"证据不足:已收集 {len(evidences)} 条,预期至少 {expected_min} 条"
        )

    # --- 条件 3:证据冲突(多条 evidence 的 raw.risk_level 不一致)---
    risk_levels: set[str] = set()
    for ev in evidences:
        raw = ev.get("raw") or {}
        rl = raw.get("risk_level") or raw.get("severity")
        if rl:
            risk_levels.add(str(rl))
    if len(risk_levels) > 1:
        reasons.append(f"证据冲突:多个 risk_level 共存 {sorted(risk_levels)}")

    # --- 条件 4:预算临界 ---
    remaining = budget - tool_rounds
    budget_threshold = max(1, int(budget * 0.2)) if budget > 0 else 1
    if remaining <= budget_threshold:
        reasons.append(
            f"预算临界:剩余 {remaining} 轮(阈值 {budget_threshold})"
        )
    if total_tokens >= TOKEN_BUDGET_THRESHOLD:
        reasons.append(
            f"token 预算临界:已用 {total_tokens} ≥ 阈值 {TOKEN_BUDGET_THRESHOLD}"
        )

    # --- 条件 5:重复 / 停滞 ---
    if len(tool_history) >= DUPLICATE_ROUNDS_THRESHOLD:
        recent = tool_history[-DUPLICATE_ROUNDS_THRESHOLD:]
        args_set = {h.get("args_summary", "") for h in recent}
        if len(args_set) == 1 and "" not in args_set:
            reasons.append(
                f"重复调用:最近 {DUPLICATE_ROUNDS_THRESHOLD} 轮 args 相同"
            )
    if tool_history:
        last = tool_history[-1]
        if not last.get("source_ids"):
            reasons.append("停滞:最近一轮无新 source_ids 产出")

    # --- 条件 6:可能完成(证据覆盖所有假设)---
    if hypotheses and len(evidences) >= len(hypotheses):
        reasons.append(
            f"可能完成:已收集 {len(evidences)} 条证据,覆盖 {len(hypotheses)} 个假设"
        )

    # --- 条件 7:需要改变方向(冲突 + 失败组合)---
    has_conflict = any("证据冲突" in r for r in reasons)
    has_failure = any("工具调用失败" in r or "工具失败" in r for r in reasons)
    if has_conflict and has_failure:
        reasons.append("需要改变方向:证据冲突且工具失败,当前路径可能无效")

    return (len(reasons) > 0, reasons)


async def deterministic_gate_node(state: dict) -> dict:
    """确定性门控节点:纯代码规则判断是否进 decision_llm。

    设计要点(对齐 §3.2.3 两段式门控):
    - 纯代码,零 LLM 调用,低成本确定性判断
    - 命中任一触发条件才进 decision_llm(省 LLM 调用)
    - 未命中则直接回 agent(继续 ReAct 循环)

    State 写入:
    - gate_triggered: bool(是否命中触发条件)
    - gate_reasons: list[str](命中的触发条件,供 decision_llm 参考)
    """
    triggered, reasons = _evaluate_gate_conditions(state)
    if triggered:
        logger.info(
            "[agent.gate] 命中触发条件,进 decision_llm: %s", reasons
        )
    return {
        "gate_triggered": triggered,
        "gate_reasons": reasons,
    }


# ============ decision_llm 节点(light 模型四选一决策)============


async def decision_llm_node(state: dict) -> dict:
    """decision_llm 节点:light 模型四选一决策(continue/replan/compact/finish)。

    设计要点(对齐 §3.2.3):
    - 仅在 deterministic_gate 命中触发条件时调用(省 LLM 调用)
    - 用 light 模型(语义判断但不需强推理,省钱),温度 0.1(门控保守)
    - 输出 DecisionSchema{action, reason, next_step}
    - action 规范化:小写,未知值降级为 continue(防 LLM 输出错误动作卡死)

    State 写入:
    - decision_result: DecisionSchema.model_dump()(graph 条件边读 action)
    - decision_history: [decision_dict](累加,可追溯)
    - finish_reason: reason(finish 时写,可追溯;非 finish 写空串覆盖)
    """
    llm_decision = await _ensure_decision_llm()
    messages = render_decision_prompt(
        state.get("current_plan"),
        state.get("investigation_summary", ""),
        state.get("evidence_pack"),
        state.get("tool_history") or [],
        state.get("gate_reasons") or [],
    )
    result = await invoke_structured_with_retry(
        llm_decision, messages, DecisionSchema, role="light",
    )
    decision_dict = (
        result.model_dump() if hasattr(result, "model_dump") else dict(result)
    )
    # 规范化 action(小写,未知降级 continue)
    action = str(decision_dict.get("action", "continue")).lower().strip()
    if action not in ("continue", "replan", "compact", "finish"):
        action = "continue"
    decision_dict["action"] = action
    finish_reason = decision_dict.get("reason", "") if action == "finish" else ""

    logger.info(
        "[agent.decision] action=%s reason=%s next_step=%s",
        action, decision_dict.get("reason", ""), decision_dict.get("next_step", ""),
    )

    return {
        "decision_result": decision_dict,
        "decision_history": [decision_dict],
        "finish_reason": finish_reason,
    }


# ============ compact 节点(结构化上下文压缩,不重写 message history)============


async def compact_node(state: dict) -> dict:
    """compact 节点:对历史调查过程生成摘要,保留核心证据,不重写 message history。

    设计要点(对齐 §3.5.3):
    - 防过度压缩:compact_count ≥ MAX_COMPACT_COUNT 时降级不压缩(直接回 agent)
    - 找 old_messages = messages[:-RECENT_MESSAGES_N](待压缩的历史)
    - 保留 recent = messages[-RECENT_MESSAGES_N:](agent_node 下轮只取这些)
    - 用 light 模型生成摘要,追加到 investigation_summary(格式 "[compact #N] summary")
    - 不重写 messages(对齐 §3.5 "不直接修改 message history"),
      靠 agent_node 在 compact_count>0 时只取 recent N 条实现 token 节省

    State 写入:
    - investigation_summary: 追加压缩摘要(格式 "[compact #N] summary\n")
    - compact_count: +1
    """
    compact_count = state.get("compact_count", 0) or 0
    # 防过度压缩:达上限降级不压缩
    if compact_count >= MAX_COMPACT_COUNT:
        logger.warning(
            "[agent.compact] compact_count=%d 达上限 %d,降级不压缩",
            compact_count, MAX_COMPACT_COUNT,
        )
        return {}

    messages = list(state.get("messages") or [])
    if len(messages) <= RECENT_MESSAGES_N:
        # 消息太少,无需压缩
        return {"compact_count": compact_count + 1}

    old_messages = messages[:-RECENT_MESSAGES_N]
    tool_history = state.get("tool_history") or []
    existing_summary = state.get("investigation_summary", "") or ""

    llm_compact = await _ensure_compact_llm()
    prompt_messages = render_compact_prompt(
        existing_summary, old_messages, tool_history,
    )
    result = await invoke_structured_with_retry(
        llm_compact, prompt_messages, CompactSummarySchema, role="light",
    )
    summary_dict = (
        result.model_dump() if hasattr(result, "model_dump") else dict(result)
    )
    summary = summary_dict.get("summary", "") or ""

    # 追加到 investigation_summary(格式 "[compact #N] summary",便于审计)
    new_count = compact_count + 1
    if existing_summary:
        updated_summary = (
            f"{existing_summary}\n[compact #{new_count}] {summary}"
        )
    else:
        updated_summary = f"[compact #{new_count}] {summary}"

    logger.info(
        "[agent.compact] compact_count=%d→%d, summary_len=%d, "
        "preserved_ids=%d, dropped=%d",
        compact_count, new_count, len(summary),
        len(summary_dict.get("preserved_evidence_ids") or []),
        summary_dict.get("dropped_count", 0),
    )

    return {
        "investigation_summary": updated_summary,
        "compact_count": new_count,
    }
