"""analysis_workflow prompts(对齐 §3.1)。

v2.1 升级:
- _SYSTEM_PROMPT 接收 evidence_pack,把检索到的证据作为参考资料注入(替代 v1 占位 context)
- 新增 _VALIDATE_PROMPT:质量门控 light 模型,检查 analysis 结论是否有 evidence 支撑
- 新增 _REPORT_PROMPT:报告生成 + citation,无引用结论标记"推测"(反幻觉)

模板变量:
- {{LOG_DATA}}:输入日志 JSON
- {{EVIDENCE_PACK}}:RAG 检索得到的证据列表(文本化呈现,content + source_id + score)
- {{ANALYSIS}}:analyze 节点的结构化输出 JSON
- {{VALIDATE_RESULT}}:validate 节点输出(missing 字段供 enrich 决策,report 不强依赖)
- {{MISSING}}:validate 缺失项,enrich 据此补检索
"""
import json
from typing import Any

from langchain_core.messages import SystemMessage

# ============ 工具函数:把 evidence_pack 序列化为可读文本 ============

def _format_evidence_pack(evidence_pack: Any) -> str:
    """把 evidence_pack(state 中的 dict)序列化为 prompt 可读文本。

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
        [检索证据] query=...,fused=True,sources=['bm25','vector']
        - [source_id=evt_001, score=0.033, type=matched_logs]
          content: ...
        - ...

    无证据时返回占位文本(让 LLM 知道没检索到东西,不要瞎编)。
    """
    if not evidence_pack:
        return "(无检索证据。所有结论必须基于输入日志,不得编造未给出的信息。)"

    # 兼容 dict / EvidencePack 实例
    if hasattr(evidence_pack, "model_dump"):
        pack_dict = evidence_pack.model_dump()
    elif isinstance(evidence_pack, dict):
        pack_dict = evidence_pack
    else:
        return f"(证据格式不支持:{type(evidence_pack).__name__})"

    evidences = pack_dict.get("evidences") or []
    if not evidences:
        return "(检索无结果。所有结论必须基于输入日志,不得编造未给出的信息。)"

    query = pack_dict.get("query", "")
    fused = pack_dict.get("fused", False)
    sources = pack_dict.get("sources") or []
    lines = [
        f"[检索证据] query={query!r}, fused={fused}, sources={sources}, 共 {len(evidences)} 条"
    ]
    for ev in evidences:
        sid = ev.get("source_id", "?")
        score = ev.get("score", 0.0)
        stype = ev.get("source_type", "unknown")
        content = (ev.get("content") or "").strip()
        # 单条 content 截断 500 字防 prompt 膨胀
        if len(content) > 500:
            content = content[:500] + "...(截断)"
        lines.append(f"- [source_id={sid}, score={score:.4f}, type={stype}]")
        lines.append(f"  content: {content}")
    return "\n".join(lines)


def _format_analysis(analysis: Any) -> str:
    """把 analyze 节点的输出(dict 或 AnalysisSchema)序列化为 JSON 文本。"""
    if not analysis:
        return "{}"
    if hasattr(analysis, "model_dump"):
        analysis = analysis.model_dump()
    try:
        return json.dumps(analysis, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(analysis)


def _format_validate_result(validate_result: Any) -> str:
    """把 validate 节点输出序列化为可读文本。"""
    if not validate_result:
        return "(未校验)"
    if hasattr(validate_result, "model_dump"):
        vr = validate_result.model_dump(by_alias=True)
    elif isinstance(validate_result, dict):
        # 兼容 pass_ / pass 两种键
        vr = dict(validate_result)
        if "pass_" in vr and "pass" not in vr:
            vr["pass"] = vr["pass_"]
    else:
        return str(validate_result)
    return json.dumps(vr, ensure_ascii=False, indent=2)


# ============ analyze 节点 prompt(扩展 v1)============

# _SYSTEM_PROMPT 基于 v1 Dify 复刻,把 {{CONTEXT}} 占位改为 {{EVIDENCE_PACK}}:
# - v1 时 retrieved_context 为空串,LLM 看不到证据
# - v2.1 注入 RAG 检索得到的 evidence_pack(带 source_id),供 LLM 引用溯源
# 其余分析原则 / 流程 / 风险等级判定 / 输出要求保持不变(对齐 Dify)
_SYSTEM_PROMPT = """这里有一份安全事件数据：

{{LOG_DATA}}

你是一名网络安全风险分析助手，请根据输入的单条 Nginx 日志进行分析。

以下是从安全知识库检索得到的参考资料（含引用 source_id）：

{{EVIDENCE_PACK}}

========================

分析原则

========================

输入日志是唯一可信事实来源。

知识库仅作为背景知识，用于解释攻击原理、补充攻击背景、提供修复建议。

严禁因为知识库出现某种攻击（例如 XSS、SQL 注入等），就判定此次日志属于该攻击。

攻击类型、风险等级、攻击是否成功，必须完全依据输入日志判断。

若日志内容与知识库冲突，以日志内容为准。

如果日志没有足够证据支持某种攻击，即使知识库检索到了相关内容，也不得判定为该攻击。

引用知识库时必须挂 source_id（例如 [source_id=evt_001]），未挂引用的结论视为推测。

========================

分析流程

========================

请严格按照以下步骤思考：

第一步：

仅根据日志提取客观事实，例如：

- 请求方法
- URL
- Query 参数
- 请求体
- User-Agent
- HTTP 状态码
- IP
- 是否命中规则

第二步：

根据第一步得到的事实，

判断：

- 是否存在攻击行为
- 攻击类型
- 攻击是否成功（若无法确认必须明确说明）

此阶段禁止依据知识库判断攻击类型。

第三步：

只有当第二步已经能够确定攻击类型后，

才允许引用知识库：

- 解释攻击原理
- 补充 ATT&CK / OWASP 等背景
- 提供修复建议

引用时必须挂 source_id；若第二步无法确认攻击类型，则忽略知识库。

========================

风险等级判定

========================

Critical

仅当日志明确证明攻击已经成功时使用，例如：

- WebShell 上传成功
- 远程命令执行成功
- 获得管理员权限
- 敏感数据泄露
- 数据库导出成功
- 服务遭到破坏

评分范围：90~100

------------------------

High

满足以下任意条件即可：

- 请求包含明显攻击载荷
- 请求访问敏感资源
- User-Agent 为 sqlmap、nikto、masscan 等自动化攻击工具
- confidence ≥0.9 且 severity 为 High

High 不要求攻击成功。

如果判定 High，

必须说明：

"攻击成功无法从现有日志确认。"

评分范围：70~89

------------------------

Medium

攻击特征明确，但危害有限，例如：

- XSS
- 登录爆破
- 路径扫描
- 目录扫描
- 敏感路径探测
- 可疑 User-Agent
- HTTP 状态异常

评分范围：40~69

------------------------

Low

轻微异常，例如：

- robots.txt
- favicon.ico
- 单次404
- 普通目录探测

评分范围：10~39

------------------------

Normal

正常业务访问，无明显攻击特征。

评分范围：0~9

========================

输出要求

========================

所有结论必须能够从日志中找到对应证据。

不得编造日志中不存在的信息。

不得引用知识库作为攻击存在的证据。

返回内容统一使用中文。"""


def render_prompt(log_data: dict, evidence_pack: Any = None) -> list:
    """渲染 analyze 节点 prompt,返回 LangChain 消息列表。

    v2.1:接收 evidence_pack(替代 v1 的 retrieved_context 字符串),
    把检索证据(带 source_id)注入 prompt,供 LLM 引用溯源。

    Dify 原始 prompt 是单一 system role,这里保持一致:整个 prompt 作为 SystemMessage。
    结构化输出由 nodes.py 的 with_structured_output(method='json_schema') 强约束,
    不在 prompt 内指示 JSON 格式。
    """
    log_text = json.dumps(log_data, ensure_ascii=False)
    evidence_text = _format_evidence_pack(evidence_pack)
    prompt = (
        _SYSTEM_PROMPT
        .replace("{{LOG_DATA}}", log_text)
        .replace("{{EVIDENCE_PACK}}", evidence_text)
    )
    return [SystemMessage(content=prompt)]


# ============ validate 节点 prompt(新增,质量门控)============

# 用 light 模型省钱:只做质量判断,不重做分析
# 输入:输入日志 + 检索证据 + analyze 输出;输出:PASS/FAIL + missing + reason
_VALIDATE_PROMPT = """你是一名安全分析质量审核员。请判断下面这份安全分析结论是否站得住脚。

========================

输入日志：

{{LOG_DATA}}

========================

检索证据（带 source_id）：

{{EVIDENCE_PACK}}

========================

待审核的分析结论：

{{ANALYSIS}}

========================

审核规则（严格执行，不得放宽）：

1. **证据支撑**：分析中提到的攻击类型、IP、载荷、风险等级等关键结论，
   必须能在输入日志或 evidence_pack 中找到对应证据。
   若关键结论无证据支撑 → pass=False，并把缺失项加入 missing。

2. **日志为准**：若分析与日志冲突（例如日志显示 200 状态码但分析判 Critical），
   判 pass=False，missing 加入"日志事实冲突"。

3. **引用溯源**：若分析引用了知识库结论但未挂 source_id，判 pass=False，
   missing 加入"引用缺失 source_id"。

4. **置信度**：risk_score 与 risk_level 不匹配（例如 risk_level=Critical 但
   risk_score=50）→ pass=False，missing 加入"评分与等级不匹配"。

5. **不放宽**：即使分析看起来合理，只要存在上述任一问题就判 False。
   只有完全无问题才判 True。

6. **不编造**：不要以"我猜应该"为理由判 True。证据不足就是 False。

========================

输出要求（结构化）：

- pass: 布尔值,True=通过门控可进 report,False=需 enrich 补证据
- missing: 缺失/有问题的证据项列表(供 enrich 决定补检索词),例如:
    ["攻击类型 SQLi 无载荷证据", "引用知识库未挂 source_id", "评分与等级不匹配"]
- reason: 一句话说明判断理由
"""


def render_validate_prompt(log_data: dict, evidence_pack: Any, analysis: Any) -> list:
    """渲染 validate 节点 prompt。"""
    log_text = json.dumps(log_data, ensure_ascii=False)
    evidence_text = _format_evidence_pack(evidence_pack)
    analysis_text = _format_analysis(analysis)
    prompt = (
        _VALIDATE_PROMPT
        .replace("{{LOG_DATA}}", log_text)
        .replace("{{EVIDENCE_PACK}}", evidence_text)
        .replace("{{ANALYSIS}}", analysis_text)
    )
    return [SystemMessage(content=prompt)]


# ============ report 节点 prompt(新增,带 citation 反幻觉)============

# 用 analysis 模型(强模型)生成最终报告,要带 source_id 引用
# 输入:输入日志 + 证据 + 分析结论 + validate 结果(可选参考)
# 输出:报告正文 + 引用到的 source_id 列表 + 未被引用的"推测"结论
_REPORT_PROMPT = """你是一名安全分析报告撰写员。请基于以下输入生成一份结构清晰、引用溯源完整的最终安全分析报告。

========================

输入日志：

{{LOG_DATA}}

========================

检索证据（带 source_id）：

{{EVIDENCE_PACK}}

========================

分析结论（结构化）：

{{ANALYSIS}}

========================

校验结果（参考，可能为空）：

{{VALIDATE_RESULT}}

========================

报告要求（严格执行）：

1. **结构**：报告分为「事件概述」「证据链」「风险判定」「修复建议」四节。

2. **引用溯源**：
   - 引用知识库/历史告警证据时，必须挂 source_id，格式：[source_id=evt_001]。
   - 引用的 source_id 必须出现在 evidence_pack 中，不得编造 source_id。
   - 把所有引用到的 source_id 写入 cited_source_ids 字段。

3. **反幻觉（不得放宽）**：
   - 无 evidence 支撑的结论必须显式标记「（推测）」，并写入 unresolved 字段。
   - 例如「攻击者可能使用自动化工具」若无证据，标记为「（推测）」。
   - 不得把推测结论当事实陈述。

4. **日志为准**：若分析与日志冲突，以日志为准，报告中说明冲突。

5. **不编造**：不得出现日志和证据中都不存在的 IP / 载荷 / 时间 / 字段。

6. **语言**：中文。

========================

输出要求（结构化）：

- report: 报告正文（含四节结构，引用挂 source_id，推测标记「（推测）」）
- cited_source_ids: 引用到的 source_id 列表
- unresolved: 无 evidence 支撑的推测结论列表
"""


def render_report_prompt(
    log_data: dict,
    evidence_pack: Any,
    analysis: Any,
    validate_result: Any = None,
) -> list:
    """渲染 report 节点 prompt。"""
    log_text = json.dumps(log_data, ensure_ascii=False)
    evidence_text = _format_evidence_pack(evidence_pack)
    analysis_text = _format_analysis(analysis)
    validate_text = _format_validate_result(validate_result)
    prompt = (
        _REPORT_PROMPT
        .replace("{{LOG_DATA}}", log_text)
        .replace("{{EVIDENCE_PACK}}", evidence_text)
        .replace("{{ANALYSIS}}", analysis_text)
        .replace("{{VALIDATE_RESULT}}", validate_text)
    )
    return [SystemMessage(content=prompt)]


# ============ enrich 节点辅助:从 missing 生成补检索词 ============

def build_enrich_query(log_data: dict, missing: list[str], enrich_count: int) -> str:
    """根据 validate 的 missing 列表 + 原始日志,生成补检索查询词。

    策略(纯代码,不进 LLM —— enrich 是定向补检索,不是 LLM 反思):
    - missing 中的关键词优先(IP / 攻击类型 / 载荷特征)
    - 第 2 次 enrich 扩时间窗(把 IP + attack_type 作为查询主体)
    - 兜底用原始日志的 IP + path 作为查询

    Args:
        log_data: 原始输入日志
        missing: validate 输出的缺失项列表
        enrich_count: 当前已 enrich 次数(0 表示第一次,1 表示第二次)

    Returns:
        补检索的查询字符串
    """
    ip = log_data.get("ip") or log_data.get("client_ip") or ""
    path = log_data.get("path") or log_data.get("url") or ""
    method = log_data.get("method") or ""
    attack_type = log_data.get("attack_type") or log_data.get("matched_type") or ""
    ua = log_data.get("user_agent") or ""

    # 从 missing 中提取关键词(简单字符串匹配)
    missing_text = " ".join(missing) if missing else ""

    parts: list[str] = []
    # 第一次 enrich:聚焦 IP + missing 中的攻击类型关键词
    if enrich_count == 0:
        if ip:
            parts.append(ip)
        if attack_type:
            parts.append(attack_type)
        # missing 中若提到 SQLi / XSS / 路径遍历 等关键词,加入查询
        keywords = ["SQL注入", "SQLi", "XSS", "路径遍历", "命令注入",
                   "扫描", "爆破", "WebShell", "敏感访问"]
        for kw in keywords:
            if kw in missing_text:
                parts.append(kw)
        if not parts:
            # 兜底:用 path 关键词
            if path:
                parts.append(path)
    else:
        # 第二次 enrich:扩时间窗语义,IP + method + attack_type
        if ip:
            parts.append(ip)
        if method:
            parts.append(method)
        if attack_type:
            parts.append(attack_type)
        if ua and "sqlmap" in ua.lower():
            parts.append("sqlmap")
        if not parts and path:
            parts.append(path)

    return " ".join(parts) if parts else (ip or path or "")
