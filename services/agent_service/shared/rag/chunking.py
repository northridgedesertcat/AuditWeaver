"""RAG 切片策略 —— 安全日志按"会话/事件"切,不按固定长度(对齐 §3.4)。

设计理由(面试能讲):
- 通用 RAG 切片:按 token 长度(如 512 token / 50 重叠),适合文档/知识库
- 安全场景切片:必须按"事件"切 —— 一个完整攻击事件(IP+时间窗+规则命中)为一片
  * 同一攻击事件的多个日志行(请求/规则命中/告警)应聚合为一片
  * 跨事件的日志行不应混在一片(否则 LLM 看到的证据逻辑混乱)
- 切片粒度直接影响 Recall@K:
  * 太细(单条日志一片):content 信息量不足,LLM 难判断
  * 太粗(多事件一片):向量语义模糊,BM25 噪声多
  * 事件粒度是安全场景的最优解

实现边界(P0-3):
- chunk_event_to_evidence: 单个 ES doc → 单个 Evidence(matched_logs / analysis_report)
- chunk_nginx_session: nginx-log-raw 按 (IP, 5min 窗口) 聚合为一片
- build_corpus_evidences: 从多个索引批量切片(供 evals/build_rag_index.py 调用)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from common.time_utils import to_epoch_millis  # 复用项目时间工具
from .result import Evidence

logger = logging.getLogger(__name__)

# nginx 会话窗口:同 IP 5 分钟内的请求聚合为一片
NGINX_SESSION_WINDOW_MS = 5 * 60 * 1000


def chunk_event_to_evidence(
    doc: dict,
    source_type: str,
) -> Evidence | None:
    """单个事件 doc → Evidence(主要给 matched_logs / analysis_report 用)。

    Args:
        doc: ES 单条 hit 或 _source dict
        source_type: 'matched_logs' / 'analysis_report' / ...

    Returns:
        Evidence 或 None(doc 无可用字段时)
    """
    src = doc.get("_source", doc) if isinstance(doc, dict) else {}
    ctx = src.get("log_context") or {}

    content = _describe_event(src, source_type)
    if not content:
        return None

    sid = str(src.get("event_id") or src.get("source_id") or doc.get("_id", "") or "")
    return Evidence(
        content=content,
        source_id=sid,
        score=0.0,  # 切片阶段无 score,建索引时由检索打分
        source_type=source_type,
        raw=src,
    )


def chunk_nginx_session(docs: list[dict]) -> list[Evidence]:
    """nginx-log-raw 按 (IP, 5min 窗口) 聚合切片。

    输入:同 IP 的多个 nginx log hit(已按时间排序)
    输出:每个时间窗一个 Evidence,content 描述该窗口内的请求序列

    实现:
        1. 按 timestamp 排序
        2. 滑动窗口:相邻请求时间差 > 5min 则开新窗
        3. 每个窗口的 content = "IP=X 在 [t1~t2] 发起 N 次请求:METHOD path status, ..."
    """
    if not docs:
        return []

    # 解析时间 + 排序
    parsed: list[tuple[int, dict]] = []
    for d in docs:
        src = d.get("_source", d) if isinstance(d, dict) else {}
        ctx = src.get("log_context") or {}
        ts = ctx.get("timestamp") or src.get("timestamp")
        if ts is None:
            continue
        try:
            ts_ms = to_epoch_millis(ts)
        except Exception:
            continue
        parsed.append((ts_ms, src))
    parsed.sort(key=lambda x: x[0])

    if not parsed:
        return []

    # 滑动窗口切片
    evidences: list[Evidence] = []
    win_start = parsed[0][0]
    win_ip = (parsed[0][1].get("log_context") or {}).get("ip", "")
    win_items: list[tuple[int, dict]] = []

    for ts, src in parsed:
        ip = (src.get("log_context") or {}).get("ip", "")
        # 新窗口触发:IP 变了 或 时间差超 5min
        if ip != win_ip or ts - win_start > NGINX_SESSION_WINDOW_MS:
            if win_items:
                ev = _build_nginx_session_evidence(win_ip, win_items)
                if ev:
                    evidences.append(ev)
            win_items = [(ts, src)]
            win_start = ts
            win_ip = ip
        else:
            win_items.append((ts, src))

    # 收尾
    if win_items:
        ev = _build_nginx_session_evidence(win_ip, win_items)
        if ev:
            evidences.append(ev)

    return evidences


def _describe_event(src: dict, source_type: str) -> str:
    """把 ES _source 拼成自然语言描述(content 字段)。

    覆盖 matched_logs / analysis_report / nginx-log-raw 三类。
    """
    ctx = src.get("log_context") or {}
    parts: list[str] = []

    atk = src.get("attack_type")
    if atk:
        parts.append(f"attack_type={atk}")

    rule_id = src.get("rule_id")
    matched_value = src.get("matched_value")
    if rule_id:
        parts.append(f"rule_id={rule_id}")
    if matched_value:
        parts.append(f"matched_value={matched_value}")

    if ctx.get("ip"):
        parts.append(f"ip={ctx['ip']}")
    if ctx.get("method"):
        path = ctx.get("path", "")
        parts.append(f'request={ctx["method"]} {path}'.rstrip())
    if ctx.get("status"):
        parts.append(f'status={ctx["status"]}')
    if ctx.get("user_agent"):
        parts.append(f'ua={ctx["user_agent"]}')

    ts = ctx.get("timestamp") or src.get("timestamp")
    if ts:
        parts.append(f'@{ts}')

    if not parts:
        # 兜底:analysis_report 等可能字段不同
        title = src.get("title") or src.get("summary") or ""
        if title:
            parts.append(str(title)[:200])
        else:
            return ""

    return " ".join(parts)


def _build_nginx_session_evidence(ip: str, items: list[tuple[int, dict]]) -> Evidence | None:
    """把一个 nginx 会话窗口拼成 Evidence。"""
    if not items:
        return None
    t_start = items[0][0]
    t_end = items[-1][0]
    # 取前 5 条请求摘要(避免 content 过长)
    req_summary: list[str] = []
    for _, src in items[:5]:
        ctx = src.get("log_context") or src
        m = ctx.get("method", "?")
        p = ctx.get("path", "?")
        s = ctx.get("status", "?")
        req_summary.append(f"{m} {p} {s}")
    if len(items) > 5:
        req_summary.append(f"...(+{len(items) - 5} more)")

    content = (
        f"ip={ip} 在 [{t_start}~{t_end}] 发起 {len(items)} 次请求: "
        + "; ".join(req_summary)
    )
    # source_id 用 ip + 时间窗起止(会话级唯一)
    sid = f"nginx_session::{ip}::{t_start}::{t_end}"
    return Evidence(
        content=content,
        source_id=sid,
        score=0.0,
        source_type="nginx-log-raw",
        raw={"ip": ip, "items": [s for _, s in items]},
    )


def build_corpus_evidences(
    matched_logs_docs: list[dict],
    nginx_logs_by_ip: dict[str, list[dict]] | None = None,
    report_docs: list[dict] | None = None,
) -> list[Evidence]:
    """从多个业务索引批量切片,供 evals/build_rag_index.py 灌 RAG 语料索引用。

    Args:
        matched_logs_docs: matched_logs 命中的安全事件 list
        nginx_logs_by_ip: nginx-log-raw 按 IP 分组的 dict(供会话切片)
        report_docs: analysis_report 报告 list(每报告一片)

    Returns:
        list[Evidence]: 全部切片,准备写入 RAG 语料索引
    """
    evidences: list[Evidence] = []

    # 1. matched_logs: 一事件一片
    for doc in matched_logs_docs:
        ev = chunk_event_to_evidence(doc, "matched_logs")
        if ev:
            evidences.append(ev)

    # 2. nginx-log-raw: 按 IP 分组做会话切片
    if nginx_logs_by_ip:
        for ip, docs in nginx_logs_by_ip.items():
            evidences.extend(chunk_nginx_session(docs))

    # 3. analysis_report: 一报告一片
    if report_docs:
        for doc in report_docs:
            ev = chunk_event_to_evidence(doc, "analysis_report")
            if ev:
                evidences.append(ev)

    logger.info(
        "[rag.chunking] 切片完成 total=%d (matched=%d nginx_sessions=%d reports=%d)",
        len(evidences),
        len(matched_logs_docs),
        sum(len(chunk_nginx_session(d)) for d in (nginx_logs_by_ip or {}).values()),
        len(report_docs or []),
    )
    return evidences
