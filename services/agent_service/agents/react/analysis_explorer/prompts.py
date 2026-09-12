"""Analysis Explorer Agent 系统提示词(对齐 §3.2 + §3.5)。

v2.1 升级:
- _SYSTEM_PROMPT 接收结构化上下文(plan / investigation_summary / evidence_pack / tool_history),
  替代 v1 的裸 SYSTEM_PROMPT(只描述工具与回答规则)
- 新增 _PLAN_PROMPT:plan 节点生成调查计划(Plan-and-Solve 范式)
- 新增 _DECISION_PROMPT:decision_llm 节点四选一(continue / replan / compact / finish)
- 新增 _COMPACT_PROMPT:compact 节点结构化压缩(保留核心证据,不重写 message history)

模板变量:
- {{PLAN}}: 当前调查计划(hypotheses / steps / expected_evidence / budget)
- {{INVESTIGATION_SUMMARY}}: 已压缩的历史调查摘要(compact 产物,首轮为空)
- {{EVIDENCE_PACK}}: 已收集的证据列表(带 source_id,供 LLM 引用溯源)
- {{TOOL_HISTORY}}: 工具调用历史摘要(全程累积,LLM 据此判断是否重复调用)
- {{USER_QUERY}}: 用户原始问题(plan 节点生成计划用)
- {{GATE_REASONS}}: deterministic_gate 命中的触发条件(decision_llm 据此决策)
- {{EXISTING_SUMMARY}}: 已有的 investigation_summary(compact 节点追加用)
- {{OLD_MESSAGES}}: 待压缩的历史消息(compact 节点摘要用)
"""
import json
from typing import Any

from langchain_core.messages import SystemMessage

# ============ 工具函数:把 state 字段序列化为 prompt 可读文本 ============


def _format_plan(plan: Any) -> str:
    """把 plan(state 中的 dict / PlanSchema)序列化为 prompt 可读文本。

    输出格式:
        [调查计划]
        假设:
        1. <假设 1>
        2. <假设 2>
        验证步骤:
        1. <步骤 1>
        2. <步骤 2>
        预期证据: <证据类型 1> / <证据类型 2>
        预算: N 轮工具调用

    无计划时返回占位文本(让 LLM 知道还没规划,不应瞎跑)。
    """
    if not plan:
        return "(尚未生成调查计划。请先完成 plan 节点再决策。)"

    if hasattr(plan, "model_dump"):
        plan = plan.model_dump()
    if not isinstance(plan, dict):
        return f"(计划格式不支持:{type(plan).__name__})"

    hypotheses = plan.get("hypotheses") or []
    steps = plan.get("steps") or []
    expected_evidence = plan.get("expected_evidence") or []
    budget = plan.get("budget", 0)

    if not hypotheses and not steps:
        return "(调查计划为空。)"

    lines = ["[调查计划]"]
    if hypotheses:
        lines.append("假设:")
        for i, h in enumerate(hypotheses, 1):
            lines.append(f"  {i}. {h}")
    if steps:
        lines.append("验证步骤:")
        for i, s in enumerate(steps, 1):
            lines.append(f"  {i}. {s}")
    if expected_evidence:
        lines.append(f"预期证据: {' / '.join(expected_evidence)}")
    lines.append(f"预算: {budget} 轮工具调用")
    return "\n".join(lines)


def _format_investigation_summary(summary: Any) -> str:
    """把 investigation_summary 序列化为 prompt 可读文本。

    summary 是 compact 节点追加生成的字符串,首轮为空。
    无摘要时返回占位文本(让 LLM 知道没有历史调查记录)。
    """
    if not summary:
        return "(尚无历史调查摘要。这是首轮调查。)"
    if not isinstance(summary, str):
        summary = str(summary)
    # 截断 1000 字防 prompt 膨胀(compact 产物本身已压缩,这里再兜底)
    if len(summary) > 1000:
        summary = summary[:1000] + "...(截断)"
    return f"[历史调查摘要]\n{summary}"


def _format_evidence_pack(evidence_pack: Any) -> str:
    """把 evidence_pack 序列化为 prompt 可读文本(参考 workflow 同名函数)。

    evidence_pack 形态:
        {
            "query": "...",
            "evidences": [
                {"content": "...", "source_id": "evt_001", "score": 0.033,
                 "source_type": "matched_logs", "raw": {...}},
                ...
            ],
            "fused": True,
            "sources": ["bm25", "vector"],
        }

    输出格式:
        [已收集证据] 共 N 条
        - [source_id=evt_001] content: ...
        - ...

    无证据时返回占位文本(让 LLM 知道还没收集到证据,不要编造)。
    单条 content 截断 300 字防 prompt 膨胀(Agent 上下文比 workflow 更紧张)。
    """
    if not evidence_pack:
        return "(尚未收集到证据。所有结论必须基于工具返回的真实数据,不得编造。)"

    if hasattr(evidence_pack, "model_dump"):
        pack_dict = evidence_pack.model_dump()
    elif isinstance(evidence_pack, dict):
        pack_dict = evidence_pack
    else:
        return f"(证据格式不支持:{type(evidence_pack).__name__})"

    evidences = pack_dict.get("evidences") or []
    if not evidences:
        return "(尚未收集到证据。所有结论必须基于工具返回的真实数据,不得编造。)"

    lines = [f"[已收集证据] 共 {len(evidences)} 条"]
    for ev in evidences:
        sid = ev.get("source_id", "?")
        content = (ev.get("content") or "").strip()
        if len(content) > 300:
            content = content[:300] + "...(截断)"
        lines.append(f"- [source_id={sid}] {content}")
    return "\n".join(lines)


def _format_tool_history(history: Any) -> str:
    """把 tool_history 序列化为 prompt 可读文本。

    tool_history 是 list[dict],每条含 tool_name / args_summary / result_summary / source_ids。
    输出格式:
        [工具调用历史] 共 N 轮
        1. QueryIPLogs(ip=1.1.1.1) → ok(10 records) [evt_001, evt_002]
        2. QuerySecurityEvents(attack_type=SQLi) → FAIL: timeout

    无历史时返回占位文本。截断最近 10 轮防 prompt 膨胀。
    """
    if not history:
        return "(尚无工具调用历史。)"
    if not isinstance(history, list):
        return f"(工具历史格式不支持:{type(history).__name__})"

    # 只取最近 10 轮(早期历史已被 compact 摘要,这里只看最近)
    recent = history[-10:]
    lines = [f"[工具调用历史] 共 {len(history)} 轮,显示最近 {len(recent)} 轮"]
    for i, h in enumerate(recent, 1):
        tool_name = h.get("tool_name", "?")
        args = h.get("args_summary", "")
        result = h.get("result_summary", "")
        sids = h.get("source_ids") or []
        sid_str = f" [{', '.join(sids[:5])}]" if sids else ""
        lines.append(f"  {i}. {tool_name}({args}) → {result}{sid_str}")
    return "\n".join(lines)


# ============ agent 节点 system prompt(改造 v1)============

# _SYSTEM_PROMPT 基于 v1,保留 3 个工具说明 + 6 条回答规则,新增结构化上下文注入:
# - v1 时只有工具说明 + 回答规则,LLM 没有计划指导,容易原地打转
# - v2.1 注入 plan / investigation_summary / evidence_pack / tool_history,
#   LLM 每轮都能看到全局调查状态,按计划执行而非盲目试错
# - 新增"引用挂 source_id,无引用标记(推测)""按计划步骤执行""所有假设验证完直接给结论"
_SYSTEM_PROMPT = """你是 AuditWeaver 的安全调查助手。用户会用自然语言询问 IP、攻击、安全事件。
你可以调用以下工具查询 Elasticsearch:
- QueryIPLogs(ip, time_range):查询某 IP 的原始 nginx 访问日志。
- QueryAnalysisResults(ip, risk_level, time_range):查询日志分析 Agent 产出的风险分析报告。
- QuerySecurityEvents(attack_type, ip, time_range):查询规则匹配命中的安全事件。

========================

当前调查上下文

========================

{{PLAN}}

{{INVESTIGATION_SUMMARY}}

{{EVIDENCE_PACK}}

{{TOOL_HISTORY}}

========================

回答规则

========================

1. 拿到工具结果后必须做归纳总结,不要把原始 JSON 直接丢给用户。
2. 风险等级术语统一为:Critical / High / Medium / Low / Normal。
3. 时间统一使用用户本地时区格式化表达(如"今天 14:32")。
4. 如果用户问的 IP 或条件没有任何数据,明确告知"未找到相关记录",不要编造。
5. 若发现高危行为,在结尾给出简短、可执行的建议(如封禁 IP、加固接口、启用 MFA)。
6. 必要时可以连续调用多个工具交叉印证,但不要无意义地重复调用。

========================

调查纪律(v2.1 新增)

========================

7. 按计划步骤执行:优先验证计划中的假设,不要跑题。
8. 引用挂 source_id:结论引用工具返回的证据时,必须挂 source_id,
   格式 [source_id=evt_001]。无引用支撑的结论标记「(推测)」。
9. 假设验证完即收尾:所有假设都已验证(成立或推翻)时,直接给出结论,
   不要继续调用工具(浪费预算)。
10. 证据为准:若工具返回的数据与你的判断冲突,以工具数据为准。
"""


def render_system_prompt(
    current_plan: Any,
    investigation_summary: Any,
    evidence_pack: Any,
    tool_history: Any,
) -> str:
    """渲染 agent 节点 system prompt,返回字符串。

    agent_node 包装成 SystemMessage + 最近 N 条消息后调 LLM。
    返回字符串(而非 list)是因为 agent_node 需要拼接 SystemMessage + recent messages,
    字符串形式更灵活(可被 agent_node 直接用 SystemMessage(content=...) 包装)。

    结构化上下文注入(对齐 §3.5):
    - plan: 调查计划(每轮提醒 LLM 当前任务,避免跑题)
    - investigation_summary: 历史调查摘要(compact 产物,首轮为空)
    - evidence_pack: 已收集证据(带 source_id,供引用溯源)
    - tool_history: 工具调用历史(避免重复调用)
    """
    plan_text = _format_plan(current_plan)
    summary_text = _format_investigation_summary(investigation_summary)
    evidence_text = _format_evidence_pack(evidence_pack)
    history_text = _format_tool_history(tool_history)
    prompt = (
        _SYSTEM_PROMPT
        .replace("{{PLAN}}", plan_text)
        .replace("{{INVESTIGATION_SUMMARY}}", summary_text)
        .replace("{{EVIDENCE_PACK}}", evidence_text)
        .replace("{{TOOL_HISTORY}}", history_text)
    )
    return prompt


# ============ plan 节点 prompt(新增,Plan-and-Solve)============

# plan 节点:根据用户问题生成结构化调查计划
# 用 analysis 模型(需强推理生成合理计划),温度 0.3(规划需一定创造性,但不要太散)
# 输出 PlanSchema{hypotheses, steps, expected_evidence, budget}
_PLAN_PROMPT = """你是 AuditWeaver 的安全调查规划员。请根据用户的安全问题,生成一份结构化调查计划。

========================

用户问题

========================

{{USER_QUERY}}

========================

可用工具

========================

- QueryIPLogs(ip, time_range):查询某 IP 的原始 nginx 访问日志
- QueryAnalysisResults(ip, risk_level, time_range):查询日志分析 Agent 产出的风险分析报告
- QuerySecurityEvents(attack_type, ip, time_range):查询规则匹配命中的安全事件

========================

规划要求

========================

1. **假设**:列出待验证的假设,每个假设是一个明确判断,例如
   "IP 1.1.1.1 在进行端口扫描"、"该 IP 关联 SQLi 攻击"。
   不要写模糊假设(如"可能有异常")。

2. **步骤**:列出验证步骤,每步对应一个工具调用意图,例如
   "查 1.1.1.1 的 nginx 日志(QueryIPLogs)"、
   "查该 IP 的安全事件(QuerySecurityEvents)"。
   步骤要可执行,不要写"分析一下"这种空话。

3. **预期证据**:列出预期需要的证据类型,供后续判断证据是否充足,例如
   "IP 的访问记录"、"攻击类型匹配"。

4. **预算**:本轮调查的工具调用上限。简单问题(单 IP 单次查询)用 3,
   复杂调查(多 IP 交叉印证)用 10。中间情况用 5。

========================

输出要求(结构化)

========================

- hypotheses: 假设列表(list[str])
- steps: 验证步骤列表(list[str])
- expected_evidence: 预期证据类型列表(list[str])
- budget: 工具调用预算(int,简单 3 / 复杂 10)
"""


def render_plan_prompt(user_query: str) -> list:
    """渲染 plan 节点 prompt,返回 LangChain 消息列表。

    单一 system role(对齐 workflow 风格),结构化输出由 nodes.py 的
    with_structured_output(method='function_calling') 强约束,不在 prompt 内指示 JSON 格式。
    """
    query = user_query or "(用户问题为空)"
    prompt = _PLAN_PROMPT.replace("{{USER_QUERY}}", query)
    return [SystemMessage(content=prompt)]


# ============ decision_llm 节点 prompt(新增,四选一决策)============

# decision_llm:仅在 deterministic_gate 命中触发条件时调用(省 LLM 调用)
# 用 light 模型(语义判断但不需强推理,省钱),温度 0.1(门控保守)
# 输出 DecisionSchema{action, reason, next_step},action ∈ continue/replan/compact/finish
_DECISION_PROMPT = """你是 AuditWeaver 的调查决策员。确定性门控已命中以下触发条件,
请基于当前调查状态,判断下一步应该 continue / replan / compact / finish 哪一个。

========================

触发条件(deterministic_gate 命中)

========================

{{GATE_REASONS}}

========================

当前调查上下文

========================

{{PLAN}}

{{INVESTIGATION_SUMMARY}}

{{EVIDENCE_PACK}}

{{TOOL_HISTORY}}

========================

决策选项(四选一)

========================

- **continue**:继续当前调查路径。适用:工具偶发失败但路径正确、
  证据还需补充但已有进展、预算仍充足。下一步给出具体工具调用建议。

- **replan**:重新规划。适用:当前假设被推翻、调查方向错误、
  证据冲突无法调和、需要换一批假设重新验证。下一步给出新方向建议。

- **compact**:压缩上下文。适用:上下文过长(token 接近阈值)、
  历史调查已积累太多轮、需要提炼核心证据再继续。
  注意:compact 不会丢失核心证据,只压缩冗余消息。

- **finish**:结束调查。适用:所有假设已验证(成立或推翻)、
  证据充足可下结论、预算耗尽无法继续、任务完成条件满足。
  下一步给出最终结论建议。

========================

决策原则

========================

1. 优先 finish:如果证据已覆盖所有假设,直接 finish,不要为了用完预算而继续。
2. 谨慎 replan:replan 会清空当前计划重新开始,成本高,只在方向错误时用。
3. compact 是手段不是目的:压缩是为了继续调查,不是为了压缩而压缩。
4. continue 是默认:如果只是偶发问题(如单次工具失败),优先 continue 重试。

========================

输出要求(结构化)

========================

- action: 决策动作,continue / replan / compact / finish 之一
- reason: 决策理由(一句话,可追溯)
- next_step: 下一步建议(具体到工具调用或新方向)
"""


def render_decision_prompt(
    current_plan: Any,
    investigation_summary: Any,
    evidence_pack: Any,
    tool_history: Any,
    gate_reasons: list[str],
) -> list:
    """渲染 decision_llm 节点 prompt,返回 LangChain 消息列表。"""
    plan_text = _format_plan(current_plan)
    summary_text = _format_investigation_summary(investigation_summary)
    evidence_text = _format_evidence_pack(evidence_pack)
    history_text = _format_tool_history(tool_history)
    if gate_reasons and isinstance(gate_reasons, list):
        reasons_text = "\n".join(f"- {r}" for r in gate_reasons)
    else:
        reasons_text = "(无明确触发条件,请基于状态判断)"
    prompt = (
        _DECISION_PROMPT
        .replace("{{GATE_REASONS}}", reasons_text)
        .replace("{{PLAN}}", plan_text)
        .replace("{{INVESTIGATION_SUMMARY}}", summary_text)
        .replace("{{EVIDENCE_PACK}}", evidence_text)
        .replace("{{TOOL_HISTORY}}", history_text)
    )
    return [SystemMessage(content=prompt)]


# ============ compact 节点 prompt(新增,结构化压缩)============

# compact:对历史调查过程生成摘要,保留核心证据,不重写 message history
# 用 light 模型(摘要要忠实,不需强推理),温度 0.0(摘要不能创造内容)
# 输出 CompactSummarySchema{summary, preserved_evidence_ids, dropped_count}
_COMPACT_PROMPT = """你是 AuditWeaver 的上下文压缩员。请对以下历史调查过程生成一份压缩摘要,
供后续 LLM 继续调查时使用。

========================

已有摘要(可能为空)

========================

{{EXISTING_SUMMARY}}

========================

待压缩的历史消息

========================

{{OLD_MESSAGES}}

========================

工具调用历史

========================

{{TOOL_HISTORY}}

========================

压缩要求(严格执行)

========================

1. **保留**:已验证的假设(成立或推翻)、关键 source_id、已尝试的路径、失败原因。
2. **丢弃**:重复的轮次、无发现的调用、原始 JSON 数据、冗余的中间推理。
3. **不编造**:摘要只能基于上述内容,不能添加未出现的信息。
4. **长度**:摘要不超过 500 字。
5. **格式**:自然语言段落,不要用 JSON,不要用 markdown 标题。

========================

输出要求(结构化)

========================

- summary: 压缩后的调查摘要(追加到 investigation_summary)
- preserved_evidence_ids: 本轮压缩涉及的核心证据 source_id 列表(便于审计)
- dropped_count: 本次压缩丢弃的消息数量
"""


def render_compact_prompt(
    existing_summary: str,
    old_messages: list,
    tool_history: list,
) -> list:
    """渲染 compact 节点 prompt,返回 LangChain 消息列表。

    old_messages 是被压缩的历史消息(list[BaseMessage]),这里序列化为文本。
    tool_history 是工具调用历史摘要(list[dict]),用 _format_tool_history 序列化。
    """
    summary_text = existing_summary or "(首轮压缩,无已有摘要)"
    # old_messages 序列化为文本(每条消息的 content)
    if old_messages:
        msg_lines = []
        for m in old_messages:
            mtype = getattr(m, "type", "msg") or "msg"
            content = getattr(m, "content", str(m))
            if isinstance(content, list):
                content = json.dumps(content, ensure_ascii=False)[:200]
            elif not isinstance(content, str):
                content = str(content)
            if len(content) > 200:
                content = content[:200] + "...(截断)"
            msg_lines.append(f"[{mtype}] {content}")
        messages_text = "\n".join(msg_lines)
    else:
        messages_text = "(无历史消息)"
    history_text = _format_tool_history(tool_history)

    prompt = (
        _COMPACT_PROMPT
        .replace("{{EXISTING_SUMMARY}}", summary_text)
        .replace("{{OLD_MESSAGES}}", messages_text)
        .replace("{{TOOL_HISTORY}}", history_text)
    )
    return [SystemMessage(content=prompt)]
