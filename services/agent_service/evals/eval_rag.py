"""RAG 离线评估脚本(对齐 RAG优化需求文档 v3 §P0-3)。

功能:
- 加载 golden_set_rag.jsonl(条目字段:query / expected_source_ids / category /
  self_event_id(可选)/ description)
- 对每条 query 跑 3 种检索:纯 BM25 / 纯 Vector / RRF 融合
- 统计指标:Recall@5 / Recall@10 / MRR / 自引用率(按 category 分桶 + 总体)
- 输出对比表到 stdout + 写入 evals/report_rag_{label}_{timestamp}.md

指标定义:
- Recall@K: top-K 召回中命中 expected_source_ids 的比例
    Recall@K = |retrieved ∩ expected| / |expected|
- MRR(Mean Reciprocal Rank): 第一个命中 expected 的 rank 的倒数均值
- 自引用率(self_ref_rate): 带 self_event_id 的 case 条目中,top-5 结果
    包含当前事件自身的比例(改造前应显著 > 0,P0-2 后 = 0)

expected_source_ids 匹配语义:
- 精确匹配:expected 与 retrieved source_id 相等
- 前缀匹配:expected 以 "::" 结尾(如 "attack_types/sqli::")时,
  匹配任何以该前缀开头的 retrieved source_id(知识库 doc 级期望,
  chunk 级 source_id = "{doc_id}::{chunk_index}")

--exclude-self:模拟 P0-2 后的生产行为(retrieve_node 传 exclude_ids=
[self_event_id]);基线跑分(改造前)不传该 flag。

运行(项目根目录,需先建好 RAG 语料索引):
    python -m services.agent_service.evals.eval_rag --label baseline
    python -m services.agent_service.evals.eval_rag --label after --exclude-self

注:依赖真实 ES + RAG 语料索引(由 build_rag_index.py 构建);
单测不依赖此脚本,此脚本供手动评估 + 面试演示用。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# sys.path 注入(对齐 tests/test_*.py 约定)
_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_SERVICE_DIR = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_AGENT_SERVICE_DIR)
for _p in (_AGENT_SERVICE_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.rag.bm25 import bm25_search  # noqa: E402
from shared.rag.embed import embed_query  # noqa: E402
from shared.rag.retriever import retrieve  # noqa: E402
from shared.rag.vector import knn_search  # noqa: E402

GOLDEN_SET_PATH = Path(_HERE) / "golden_set_rag.jsonl"
REPORT_DIR = Path(_HERE)

CATEGORIES = ["case", "knowledge"]
METHODS = ["bm25", "vector", "rrf"]
# 自引用率统计的 top-K(对齐生产 RAG_CONFIG['top_k']=5)
SELF_REF_K = 5


def load_golden_set(path: Path | None = None) -> list[dict]:
    """加载 golden set(jsonl 每行一个 {query, expected_source_ids, category, ...})。"""
    p = path or GOLDEN_SET_PATH
    items: list[dict] = []
    with open(p, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning("[eval_rag] golden_set 第 %d 行解析失败: %s", line_no, e)
                continue
            if "query" not in item or "expected_source_ids" not in item:
                logger.warning("[eval_rag] golden_set 第 %d 行缺字段,跳过", line_no)
                continue
            item.setdefault("category", "case")
            items.append(item)
    logger.info(
        "[eval_rag] 加载 golden set %d 条 (case=%d knowledge=%d)",
        len(items),
        sum(1 for i in items if i["category"] == "case"),
        sum(1 for i in items if i["category"] == "knowledge"),
    )
    return items


def _match_id(retrieved_id: str, expected_id: str) -> bool:
    """单条 expected 匹配:精确匹配;expected 以 '::' 结尾时前缀匹配(doc 级期望)。"""
    if expected_id.endswith("::"):
        return retrieved_id.startswith(expected_id)
    return retrieved_id == expected_id


def recall_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    """Recall@K:top-K 命中 expected 的比例(每个 expected 条目至多计 1 次)。"""
    if not expected_ids:
        return 0.0
    top_k_list = retrieved_ids[:k]
    hit = sum(1 for exp in set(expected_ids) if any(_match_id(r, exp) for r in top_k_list))
    return hit / len(set(expected_ids))


def mrr(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    """MRR:第一个命中 expected 的 rank 的倒数;无命中返回 0。"""
    expected = set(expected_ids)
    for i, sid in enumerate(retrieved_ids, start=1):
        if any(_match_id(sid, exp) for exp in expected):
            return 1.0 / i
    return 0.0


def is_self_referenced(retrieved_ids: list[str], self_event_id: str) -> bool:
    """top-SELF_REF_K 结果是否包含当前事件自身(自引用判定)。"""
    return self_event_id in retrieved_ids[:SELF_REF_K]


def eval_method(
    method: str,
    query: str,
    top_k: int,
    exclude_ids: list[str] | None = None,
) -> list[str]:
    """跑单种检索方法,返回 source_id 列表。

    method: 'bm25' / 'vector' / 'rrf'
    exclude_ids: P0-2 自引用排除(仅 --exclude-self 模式传入;
        基线运行时运行时尚未支持该参数,保持旧签名调用)
    """
    if method == "bm25":
        if exclude_ids:
            evs = bm25_search(query, top_k=top_k, exclude_ids=exclude_ids)
        else:
            evs = bm25_search(query, top_k=top_k)
        return [e.source_id for e in evs]
    if method == "vector":
        emb = embed_query(query)
        if exclude_ids:
            evs = knn_search(emb, top_k=top_k, exclude_ids=exclude_ids)
        else:
            evs = knn_search(emb, top_k=top_k)
        return [e.source_id for e in evs]
    if method == "rrf":
        if exclude_ids:
            pack = retrieve(query, top_k=top_k, exclude_ids=exclude_ids)
        else:
            pack = retrieve(query, top_k=top_k)
        return pack.source_ids
    raise ValueError(f"未知 method: {method}")


def _new_metrics() -> dict:
    return {"recall@5": 0.0, "recall@10": 0.0, "mrr": 0.0, "count": 0}


def run_eval(top_k: int = 10, exclude_self: bool = False) -> dict:
    """跑全量评估。

    Returns:
        {method: {"overall": metrics, "case": metrics, "knowledge": metrics,
                  "self_ref_hits": int, "self_ref_total": int}}
    """
    golden = load_golden_set()
    results: dict[str, dict] = {
        m: {**{c: _new_metrics() for c in CATEGORIES}, "overall": _new_metrics(),
            "self_ref_hits": 0, "self_ref_total": 0}
        for m in METHODS
    }

    for item in golden:
        query = item["query"]
        expected = item["expected_source_ids"]
        category = item.get("category", "case")
        self_event_id = item.get("self_event_id")
        exclude_ids = [self_event_id] if (exclude_self and self_event_id) else None

        for m in METHODS:
            try:
                retrieved = eval_method(m, query, top_k=top_k, exclude_ids=exclude_ids)
            except Exception as e:
                logger.warning(
                    "[eval_rag] method=%s query=%s 失败: %s: %s",
                    m, query[:40], type(e).__name__, e,
                )
                continue
            for bucket in ("overall", category):
                r = results[m][bucket]
                r["recall@5"] += recall_at_k(retrieved, expected, 5)
                r["recall@10"] += recall_at_k(retrieved, expected, 10)
                r["mrr"] += mrr(retrieved, expected)
                r["count"] += 1
            # 自引用统计(带 self_event_id 的条目;top-K 语义见 SELF_REF_K)
            if self_event_id:
                results[m]["self_ref_total"] += 1
                if is_self_referenced(retrieved, self_event_id):
                    results[m]["self_ref_hits"] += 1

    # 取平均(按成功次数;失败的 query 不计入分母)
    for m in METHODS:
        for bucket in ["overall"] + CATEGORIES:
            r = results[m][bucket]
            c = r["count"] or 1
            r["recall@5"] = r["recall@5"] / c
            r["recall@10"] = r["recall@10"] / c
            r["mrr"] = r["mrr"] / c
    return results


def format_report(results: dict, top_k: int, exclude_self: bool, label: str) -> str:
    """生成 Markdown 报告(总体 + 分桶 + 自引用率)。"""
    mode = "exclude_self=True(模拟 P0-2 后生产行为)" if exclude_self \
        else "exclude_self=False(改造前基线行为)"
    lines = [
        "# RAG 检索评估报告",
        "",
        f"生成时间: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"标签: {label}",
        f"top_k 参数: {top_k}",
        f"自引用排除: {mode}",
        "",
        "## 总体指标",
        "",
        "| Method | Recall@5 | Recall@10 | MRR | 成功 query 数 | 自引用率(top-5) |",
        "|---|---|---|---|---|---|",
    ]
    for m in METHODS:
        r = results[m]
        sr = (r["self_ref_hits"] / r["self_ref_total"]) if r["self_ref_total"] else 0.0
        lines.append(
            f"| {m} | {r['overall']['recall@5']:.4f} | {r['overall']['recall@10']:.4f} "
            f"| {r['overall']['mrr']:.4f} | {int(r['overall']['count'])} | {sr:.4f} |"
        )

    lines.extend(["", "## 分桶指标(case / knowledge)", ""])
    for cat in CATEGORIES:
        lines.append(f"### {cat} 查询")
        lines.append("")
        lines.append("| Method | Recall@5 | Recall@10 | MRR | 成功 query 数 |")
        lines.append("|---|---|---|---|---|")
        for m in METHODS:
            r = results[m][cat]
            lines.append(
                f"| {m} | {r['recall@5']:.4f} | {r['recall@10']:.4f} | {r['mrr']:.4f} | {int(r['count'])} |"
            )
        lines.append("")

    lines.extend([
        "## 指标说明",
        "- Recall@K: top-K 命中 expected_source_ids 的比例(expected 以 '::' 结尾为 doc 级前缀匹配)",
        "- MRR: 第一个命中 expected 的 rank 倒数均值",
        f"- 自引用率: 带 self_event_id 的 case 条目中,top-{SELF_REF_K} 结果含自身的比例"
        "(改造前应 > 0;P0-2 exclude_ids 后应为 0)",
        "",
        "## 解读指引",
        "- RRF 应在 Recall@K 上不弱于两路单路(融合优势)",
        "- BM25 强在字段精确(attack_type / IP),Vector 弱在这些场景",
        "- knowledge 桶:基线(无知识语料)应为 0,知识库落地后 Recall@5 目标 ≥ 0.8",
        "- case 桶:自引用率基线应显著 > 0,改造后(exclude_self)应为 0 且 Recall 不劣化(±2%)",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="RAG 检索离线评估")
    parser.add_argument("--top_k", type=int, default=10, help="检索候选数(默认 10)")
    parser.add_argument(
        "--exclude-self", action="store_true",
        help="模拟 P0-2 后生产行为:对带 self_event_id 的条目传 exclude_ids",
    )
    parser.add_argument(
        "--label", type=str, default="run",
        help="报告标签(baseline / after),用于命名 report_rag_{label}_{ts}.md",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    logger.info(
        "[eval_rag] 开始评估 top_k=%d exclude_self=%s label=%s",
        args.top_k, args.exclude_self, args.label,
    )
    results = run_eval(top_k=args.top_k, exclude_self=args.exclude_self)
    report = format_report(results, args.top_k, args.exclude_self, args.label)

    # 打印到 stdout
    print(report)

    # 写入 evals/report_rag_{label}_{timestamp}.md
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"report_rag_{args.label}_{ts}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("[eval_rag] 报告已写入: %s", report_path)


if __name__ == "__main__":
    main()
