"""Reciprocal Rank Fusion(RRF)—— 多路检索结果融合的纯函数。

公式(对齐设计 §3.4):
    score(d) = sum_over_routes( 1 / (k + rank_i(d)) )

    - d: 某个文档(Evidence),按 source_id 去重
    - rank_i(d): d 在第 i 路中的排名(从 1 开始,第 0 位 rank=1)
    - k: 平滑参数,默认 60(经典值,无权重调参负担)

特性:
    - 纯函数:input = 多路 ranked list, output = 融合后 ranked list,无 IO,易测
    - 同输入同输出(确定性排序)
    - 不依赖原始 _score 的绝对值(只看 rank),天然适配 BM25 + Vector 两路分数量纲不同的情况
    - source_id 相同的 Evidence 视为同一文档,合并 raw(保留首次出现的)

面试能讲什么:
    - 为什么 RRF 而不是加权融合:BM25 的 _score 与 Vector 的 cosine 量纲不同,加权需调参;
      RRF 只看 rank,无量纲问题,k=60 是经验默认值
    - 为什么 k=60:Cormack et al. 2009 经验值,对 top-100 内的排名差异平滑合适
    - 局限:不考虑原始分数差距(第 1 名和第 2 名 rank 都差 1,但 _score 可能差 10x)
"""
from __future__ import annotations

from .result import Evidence


def rrf_fusion(
    ranked_lists: list[list[Evidence]],
    k: int = 60,
    top_k: int | None = None,
) -> list[Evidence]:
    """RRF 融合多路 ranked list。

    Args:
        ranked_lists: 多路检索结果,每路已按 score 降序排好(Evidence.score 高在前)
            注意:本函数只看 list 顺序(rank),不看 score 数值
        k: 平滑参数,默认 60
        top_k: 返回前 top_k 条,None=返回全部融合结果

    Returns:
        list[Evidence]: 融合并按 RRF 累计分数降序排序的 Evidence 列表
        每条 Evidence.score 已被替换为 RRF 累计分数
        source_id 相同的合并为一条(保留首次出现的 content/raw/source_type)

    确定性保证:
        - 同输入必同输出(同 source_id 集合 + 同 rank 分布 → 同累计分数)
        - 分数相同按 source_id 字典序做次级排序(避免随机)
    """
    if not ranked_lists:
        return []

    # 累计分数 + 首次出现的 Evidence(用于回填 raw/content)
    accumulated: dict[str, float] = {}
    first_evidence: dict[str, Evidence] = {}

    for route_idx, ranked in enumerate(ranked_lists):
        if not ranked:
            continue
        for rank, ev in enumerate(ranked, start=1):
            # source_id 为空的兜底:用 content hash 作为 key(避免空 id 互相吞)
            key = ev.source_id or _content_key(ev, route_idx, rank)
            contribution = 1.0 / (k + rank)
            accumulated[key] = accumulated.get(key, 0.0) + contribution
            if key not in first_evidence:
                first_evidence[key] = ev

    # 组装融合后的 Evidence(score 替换为 RRF 累计)
    fused: list[Evidence] = []
    for key, total_score in accumulated.items():
        ev = first_evidence[key]
        # 复制一份,避免修改输入(score 替换)
        fused.append(
            Evidence(
                content=ev.content,
                source_id=ev.source_id,
                score=total_score,
                source_type=ev.source_type,
                raw=ev.raw,
            )
        )

    # 排序:RRF 分数降序,次级 source_id 字典序(确定性)
    fused.sort(key=lambda e: (-e.score, e.source_id))

    if top_k is not None and top_k >= 0:
        return fused[:top_k]
    return fused


def _content_key(ev: Evidence, route_idx: int, rank: int) -> str:
    """source_id 为空时的兜底 key:用 content 前 80 字 + route/rank 唯一化。

    注意:这会导致不同路里同 content 的 Evidence 不被合并,
    但空 source_id 本身就是异常情况(RAG 索引应保证 source_id 非空),
    这里只是防 crash,不追求去重准确性。
    """
    snippet = (ev.content or "")[:80]
    return f"__empty_sid__::{route_idx}::{rank}::{snippet}"
