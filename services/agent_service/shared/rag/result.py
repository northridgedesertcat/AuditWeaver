"""RAG 检索结果数据结构(对齐设计 §3.4 / §3.5 Evidence Pack)。

核心概念:
- Evidence: 单条检索结果,带 content / source_id / score / source_type / raw
- EvidencePack: list[Evidence] 的轻量容器,携带 fusion 元信息(查询词/是否融合)

设计要点:
- source_id 是引用溯源(citation)的锚点,无引用结论须标记"推测"(反幻觉)
- score 在 RRF 融合后是 1/(k+rank) 的累计;单路检索时是 ES _score
- raw 透传 ES _source,LLM 进一步查询时可用,但默认不灌入 prompt(防 context 爆炸)
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """单条检索证据。

    字段说明:
    - content: 用于 BM25 检索 / 喂给 LLM 的证据文本(已切片后的自然语言描述)
    - source_id: 引用溯源锚点,优先 event_id,次选 ES _id
    - score: RRF 融合分数(累计 1/(k+rank))或单路原始 ES _score
    - source_type: 来源类型(matched_logs / nginx-log-raw / analysis_report / ...),用于 citation 分类
    - raw: 原始 ES _source(可选),供 LLM 进一步查询用,不默认灌入 prompt
    """

    content: str = Field(description="证据文本,已切片后的自然语言描述")
    source_id: str = Field(description="引用溯源锚点(event_id / _id)")
    score: float = Field(default=0.0, description="RRF 融合分数或单路 ES _score")
    source_type: str = Field(default="unknown", description="来源类型,用于 citation 分类")
    raw: Optional[dict[str, Any]] = Field(
        default=None,
        description="原始 ES _source,可选,供 LLM 进一步查询;不默认灌入 prompt",
    )

    model_config = {"arbitrary_types_allowed": True}


class EvidencePack(BaseModel):
    """Evidence Pack 容器(对齐 §3.5 Context Engineering)。

    Agent / Workflow 把 EvidencePack 注入 state.evidence_pack,
    后续节点(analyze/validate/report)按 source_id 引用,无引用结论标记"推测"。
    """

    query: str = Field(description="原始查询词,用于追溯")
    evidences: list[Evidence] = Field(default_factory=list, description="top-K 证据列表")
    fused: bool = Field(default=False, description="是否经 RRF 融合(True=多路, False=单路")
    sources: list[str] = Field(default_factory=list, description="参与融合的来源类型列表")

    @property
    def source_ids(self) -> list[str]:
        """返回所有 evidence 的 source_id,用于 citation 列表。"""
        return [e.source_id for e in self.evidences]

    @property
    def is_empty(self) -> bool:
        return not self.evidences


def evidence_from_es_hit(
    hit: dict,
    source_type: str,
    score: float | None = None,
    content_field: str = "content",
) -> Evidence:
    """从 ES 搜索结果 hit 构造 Evidence。

    Args:
        hit: ES hit 单条,形如 {"_id": "...", "_score": 0.7, "_source": {...}}
        source_type: 来源类型(索引名 / 业务分类)
        score: 显式分数(优先),否则取 hit["_score"]
        content_field: _source 中用作 content 的字段,默认 "content"(RAG 索引专用字段)

    优先级:
        source_id = _source.event_id > _source.source_id > _id
        content = _source[content_field] > 拼接 _source 的 fallback 字段
    """
    src = (hit or {}).get("_source") or {}
    sid = (
        src.get("event_id")
        or src.get("source_id")
        or hit.get("_id")
        or ""
    )
    content = src.get(content_field) or _fallback_content(src, source_type)
    # source_type 优先从 _source 取(RAG 索引 doc 自带 source_type 字段),
    # 否则用传入的索引名兜底(直查业务索引场景)
    actual_source_type = src.get("source_type") or source_type
    return Evidence(
        content=content or "",
        source_id=str(sid) if sid else "",
        score=float(score if score is not None else (hit.get("_score") or 0.0)),
        source_type=actual_source_type,
        raw=src,
    )


def _fallback_content(src: dict, source_type: str) -> str:
    """当 _source 没有 content 字段时,从业务字段拼出描述性文本。

    用于兼容直接查 matched_logs / nginx-log-raw(没有 RAG 切片 content 字段)的场景。
    """
    ctx = src.get("log_context") or {}
    parts: list[str] = []
    atk = src.get("attack_type")
    if atk:
        parts.append(f"[{atk}]")
    if src.get("rule_id"):
        parts.append(f"rule={src['rule_id']}")
    if ctx.get("ip"):
        parts.append(f"ip={ctx['ip']}")
    if ctx.get("method"):
        parts.append(f"{ctx['method']} {ctx.get('path', '')}".rstrip())
    if ctx.get("status"):
        parts.append(f"status={ctx['status']}")
    if ctx.get("matched_value"):
        parts.append(f"matched={ctx['matched_value']}")
    if not parts:
        # 最后兜底:用 str(src) 前 200 字
        return str(src)[:200]
    return " ".join(parts)
