"""analysis_workflow 节点实现(对齐 §3.1)。

v2.1 升级:从单节点(analyze)扩展到五节点流水线:
- retrieve_node: 纯代码,调 shared.rag.retrieve,把 evidence_pack 灌入 state(不进 LLM)
- analyze_node: LLM + with_structured_output(AnalysisSchema),输入含 evidence_pack
- validate_node: light 模型质量门控,输出 PASS/FAIL + missing + reason
- enrich_node: 按 missing 定向补检索(纯代码,不进 LLM),写回 evidence_pack + enrich_count+1
- report_node: analysis 模型生成最终报告,带 source_id 引用 + 推测标记

LLM 调用契约:
- analyze / report: get_llm(role='analysis') 强模型
- validate: get_llm(role='light') 弱模型(省钱,质量判断不需强推理)
- 所有结构化输出走 invoke_structured_with_retry(解析失败附加错误反馈重试)

State 字段读写(对齐 state.py):
- evidence_pack: dict(EvidencePack.model_dump() 形式),retrieve / enrich 写,其余读
- validate_result: dict,validate 写,enrich/report 读
- enrich_count: int,enrich 写(显式 +1)
- report: str,report 写
"""
import asyncio
import json
import logging

from langchain_core.language_models import BaseChatModel

from shared.llm.factory import get_llm
from shared.llm.retry import invoke_structured_with_retry
from shared.rag import EvidencePack, retrieve as rag_retrieve
from .config.settings import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    MAX_ENRICH_COUNT,
    RAG_TOP_K,
    TEMPERATURE,
    VALIDATE_TEMPERATURE,
)
from .prompts import (
    build_enrich_query,
    render_prompt,
    render_report_prompt,
    render_validate_prompt,
)
from .schema import AnalysisSchema, ReportSchema, ValidateSchema

logger = logging.getLogger(__name__)

# ============ LLM 懒加载缓存(进程内单例,避免每次节点调用重新初始化)============

_llm_structured: BaseChatModel | None = None  # analyze 节点用(强模型 + function_calling)
_llm_validate: BaseChatModel | None = None     # validate 节点用(light 模型)
_llm_report: BaseChatModel | None = None       # report 节点用(强模型 + function_calling)
_init_lock = asyncio.Lock()


async def _ensure_analyze_llm() -> BaseChatModel:
    """懒加载 analyze 节点的结构化输出 LLM,只初始化一次。

    使用 with_structured_output(method='function_calling'):
    - schema 转为 tool 定义由模型 tool_calls 回填,不依赖 response_format
    - DeepSeek 实测不支持 response_format json_schema(400 "This response_format
      type is unavailable now"),function calling 则全厂商(DeepSeek/OpenAI/ollama)支持
    - 不支持 streaming(结构化输出与 streaming 不兼容)
    """
    global _llm_structured
    if _llm_structured is not None:
        return _llm_structured
    async with _init_lock:
        if _llm_structured is not None:
            return _llm_structured
        llm = get_llm(
            role="analysis",
            temperature=TEMPERATURE,
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            streaming=False,
        )
        _llm_structured = llm.with_structured_output(
            AnalysisSchema, method="function_calling"
        )
        return _llm_structured


async def _ensure_validate_llm() -> BaseChatModel:
    """懒加载 validate 节点的 light LLM,只初始化一次。

    validate 是质量门控,不需强推理,用 light 模型省钱。
    """
    global _llm_validate
    if _llm_validate is not None:
        return _llm_validate
    async with _init_lock:
        if _llm_validate is not None:
            return _llm_validate
        llm = get_llm(
            role="light",
            temperature=VALIDATE_TEMPERATURE,
            streaming=False,
        )
        _llm_validate = llm.with_structured_output(
            ValidateSchema, method="function_calling"
        )
        return _llm_validate


async def _ensure_report_llm() -> BaseChatModel:
    """懒加载 report 节点的结构化输出 LLM,只初始化一次。

    report 需要强模型生成带 citation 的报告,用 analysis 角色。
    """
    global _llm_report
    if _llm_report is not None:
        return _llm_report
    async with _init_lock:
        if _llm_report is not None:
            return _llm_report
        llm = get_llm(
            role="analysis",
            temperature=TEMPERATURE,
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            streaming=False,
        )
        _llm_report = llm.with_structured_output(
            ReportSchema, method="function_calling"
        )
        return _llm_report


# ============ retrieve 节点(纯代码,调 RAG)============

def _build_retrieve_query(log_data: dict) -> str:
    """从原始日志构建检索查询。

    策略:把日志的核心字段拼成自然语言描述,供 RAG 语义检索。
    - IP / path / method / 状态码 / matched_type / user_agent
    - 不直接 dump JSON(避免字段名干扰语义检索)
    """
    parts: list[str] = []
    ip = log_data.get("ip") or log_data.get("client_ip") or ""
    path = log_data.get("path") or log_data.get("url") or ""
    method = log_data.get("method") or ""
    status = log_data.get("status") or log_data.get("status_code") or ""
    matched = (
        log_data.get("matched_type")
        or log_data.get("attack_type")
        or ""
    )
    ua = log_data.get("user_agent") or ""

    if matched:
        parts.append(matched)
    if ip:
        parts.append(f"IP {ip}")
    if method and path:
        parts.append(f"{method} {path}")
    if status:
        parts.append(f"status {status}")
    if ua:
        # UA 截断 100 字防查询膨胀
        parts.append(f"UA {ua[:100]}")

    return " ".join(parts) if parts else json.dumps(log_data, ensure_ascii=False)


async def retrieve_node(state: dict) -> dict:
    """retrieve 节点:调 RAG 把 evidence_pack 灌入 state(纯代码,不进 LLM)。

    设计要点(对齐 §3.1):
    - 纯代码节点,零 LLM 调用,成本+确定性
    - 是流水线固定环节,不是 Agent 动态选工具
    - 检索失败(ES 不可用/索引未建)返回空 pack,后续节点自然降级
      (analyze 节点看到无证据仍能基于日志做分析,只是没有引用)
    - embed 配置错会抛 LLMError(配置问题不静默,对齐项目原则)
    """
    log_data = state.get("log_data", {}) or {}
    query = _build_retrieve_query(log_data)
    logger.info("[workflow.retrieve] query=%r top_k=%d", query[:80], RAG_TOP_K)

    try:
        pack: EvidencePack = rag_retrieve(query, top_k=RAG_TOP_K)
    except Exception as e:
        # RAG 检索失败:记日志但不抛(让 analyze 节点降级跑下去)
        # 注:embed_query 配置错会抛 LLMConfigError,这里捕获是为了让
        # workflow 在 RAG 不可用时仍能基于日志做单次 LLM 分析(降级路径)
        logger.error(
            "[workflow.retrieve] RAG 检索失败,降级为空 evidence_pack: %s: %s",
            type(e).__name__, e,
        )
        pack = EvidencePack(query=query, evidences=[], fused=False, sources=[])

    return {"evidence_pack": pack.model_dump(), "retrieved_context": _format_pack_as_context(pack)}


def _format_pack_as_context(pack: EvidencePack) -> str:
    """把 EvidencePack 转成简短文本,写入 state.retrieved_context(向后兼容 v1 字段)。

    v1 时 retrieved_context 是给 analyze_node 看的字符串,v2.1 analyze_node 改读
    evidence_pack(retrieve 节点写入)。retrieved_context 保留是为了向后兼容
    (例如 v1 注册的下游消费者),内容是 evidence_pack 的简短摘要。
    """
    if pack.is_empty:
        return ""
    lines = [f"检索到 {len(pack.evidences)} 条证据,query={pack.query!r}"]
    for ev in pack.evidences[:3]:  # 只取前 3 条做摘要,避免字段膨胀
        lines.append(f"- [{ev.source_id}] {ev.content[:80]}")
    return "\n".join(lines)


# ============ analyze 节点(改造 v1:输入含 evidence_pack)============

async def analyze_node(state: dict) -> dict:
    """LLM 分析节点:基于日志 + evidence_pack(RAG 检索证据),产出结构化分析。

    v2.1 改造(对齐 §3.1):
    - 输入:state.log_data + state.evidence_pack(替代 v1 的 retrieved_context)
    - prompt 注入证据(带 source_id),LLM 可引用溯源
    - 输出仍为 AnalysisSchema(向后兼容 v1)

    结构化输出解析失败时,走 invoke_structured_with_retry 重试(附加错误反馈)。
    """
    llm_structured = await _ensure_analyze_llm()
    messages = render_prompt(
        state.get("log_data", {}),
        state.get("evidence_pack"),
    )
    result = await invoke_structured_with_retry(
        llm_structured, messages, AnalysisSchema, role="analysis",
    )
    if hasattr(result, "model_dump"):
        return {"analysis": result.model_dump()}
    return {"analysis": dict(result)}


# ============ validate 节点(light 模型质量门控)============

async def validate_node(state: dict) -> dict:
    """质量门控节点:用 light 模型检查 analysis 结论是否有 evidence 支撑。

    输出 ValidateSchema{pass, missing, reason}:
    - pass=True → 路由到 report
    - pass=False → 路由到 enrich(根据 missing 补检索)

    设计要点(对齐 §3.1):
    - 用 light 模型省钱(质量判断不需强推理)
    - 输出结构化,missing 字段供 enrich 决策补检索词
    - 不重做分析,只做审核
    """
    llm_validate = await _ensure_validate_llm()
    messages = render_validate_prompt(
        state.get("log_data", {}),
        state.get("evidence_pack"),
        state.get("analysis"),
    )
    result = await invoke_structured_with_retry(
        llm_validate, messages, ValidateSchema, role="light",
    )
    # 序列化为 dict 写入 state(by_alias=True 让键为 "pass" 而非 "pass_")
    if hasattr(result, "model_dump"):
        return {"validate_result": result.model_dump(by_alias=True)}
    return {"validate_result": dict(result)}


# ============ enrich 节点(纯代码补检索)============

async def enrich_node(state: dict) -> dict:
    """enrich 节点:按 validate.missing 定向补检索(纯代码,不进 LLM)。

    设计要点(对齐 §3.1):
    - 不是 LLM 反思,是定向补检索(换词/扩时间窗)
    - enrich_count 显式 +1 写回 state,graph 条件边据此防死循环
    - 补检索得到的 evidence_pack 与原 pack 合并(去重 by source_id),
      保留更全面的证据供下一轮 analyze
    - enrich_count 达 MAX_ENRICH_COUNT 时,graph 条件边强制走 report(不再 enrich)
    """
    log_data = state.get("log_data", {}) or {}
    validate_result = state.get("validate_result", {}) or {}
    missing = validate_result.get("missing", []) or []
    enrich_count = state.get("enrich_count", 0) or 0

    # 生成补检索查询词
    new_query = build_enrich_query(log_data, missing, enrich_count)
    logger.info(
        "[workflow.enrich] count=%d query=%r missing=%s",
        enrich_count, new_query[:80], missing,
    )

    # 调 RAG 补检索
    try:
        new_pack: EvidencePack = rag_retrieve(new_query, top_k=RAG_TOP_K)
    except Exception as e:
        logger.error(
            "[workflow.enrich] 补检索失败,保留原 evidence_pack: %s: %s",
            type(e).__name__, e,
        )
        return {"enrich_count": enrich_count + 1}

    # 合并新旧 evidence_pack(去重 by source_id)
    old_pack_dict = state.get("evidence_pack") or {}
    old_evidences = old_pack_dict.get("evidences", []) if old_pack_dict else []
    new_evidences = new_pack.evidences

    # 去重:用 source_id 作为唯一键(空 source_id 用 content 兜底)
    seen_ids: set[str] = set()
    merged: list[dict] = []
    for ev in old_evidences + [e.model_dump() for e in new_evidences]:
        sid = ev.get("source_id") or ev.get("content", "")[:50]
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        merged.append(ev)

    # 合并后的 pack 元信息
    merged_pack = {
        "query": f"{old_pack_dict.get('query', '')} + {new_pack.query}".strip(" +"),
        "evidences": merged,
        "fused": old_pack_dict.get("fused", False) or new_pack.fused,
        "sources": list(
            set((old_pack_dict.get("sources") or []) + new_pack.sources)
        ),
    }

    logger.info(
        "[workflow.enrich] 合并后 evidence_pack: old=%d new=%d merged=%d",
        len(old_evidences), len(new_evidences), len(merged),
    )

    return {
        "evidence_pack": merged_pack,
        "enrich_count": enrich_count + 1,
        "retrieved_context": _format_pack_as_context_dict(merged_pack),
    }


def _format_pack_as_context_dict(pack_dict: dict) -> str:
    """从已合并的 evidence_pack(dict)生成简短文本(向后兼容 v1 retrieved_context)。"""
    evidences = pack_dict.get("evidences") or []
    if not evidences:
        return ""
    lines = [f"检索到 {len(evidences)} 条证据,query={pack_dict.get('query', '')!r}"]
    for ev in evidences[:3]:
        lines.append(f"- [{ev.get('source_id', '?')}] {(ev.get('content') or '')[:80]}")
    return "\n".join(lines)


# ============ report 节点(强模型生成最终报告 + citation)============

async def report_node(state: dict) -> dict:
    """report 节点:生成最终报告,带 source_id 引用 + 推测标记(反幻觉)。

    设计要点(对齐 §3.1):
    - 用 analysis 模型(强模型)生成报告
    - 报告引用必须挂 source_id,且 source_id 必须在 evidence_pack 中
    - 无 evidence 支撑的结论必须标记「（推测）」,并写入 unresolved 字段
    - 输出 ReportSchema{report, cited_source_ids, unresolved}
    - 最终写回 state.report(字符串,供下游消费者直接用)
    """
    llm_report = await _ensure_report_llm()
    messages = render_report_prompt(
        state.get("log_data", {}),
        state.get("evidence_pack"),
        state.get("analysis"),
        state.get("validate_result"),
    )
    result = await invoke_structured_with_retry(
        llm_report, messages, ReportSchema, role="analysis",
    )
    if hasattr(result, "model_dump"):
        data = result.model_dump()
    else:
        data = dict(result)
    # state.final_report 存报告正文(字符串),cited_source_ids/unresolved 暂不下发
    # (下游 consumers 主要消费 final_report 文本;若需要引用列表,可后续扩展 state 字段)
    # 注:字段名 final_report 而非 report,避免与 LangGraph 节点名 "report" 冲突
    return {"final_report": data.get("report", "")}
