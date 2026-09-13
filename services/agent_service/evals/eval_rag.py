"""RAG 离线评估脚本(对齐设计 §3.8 Evaluation)。

功能:
- 加载 golden_set_rag.jsonl
- 对每条 query 跑 3 种检索:纯 BM25 / 纯 Vector / RRF 融合
- 统计指标:Recall@5 / Recall@10 / MRR
- 输出对比表到 stdout + 写入 evals/report_rag_{timestamp}.md

指标定义:
- Recall@K: top-K 召回中命中 expected_source_ids 的比例
    Recall@K = |retrieved ∩ expected| / |expected|
- MRR(Mean Reciprocal Rank): 第一个命中 expected 的 rank 的倒数均值
    MRR = mean(1 / rank_first_hit)

运行(项目根目录,需先建好 RAG 语料索引):
    python -m services.agent_service.evals.eval_rag
    python -m services.agent_service.evals.eval_rag --top_k 10

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


def load_golden_set(path: Path | None = None) -> list[dict]:
    """加载 golden set(jsonl 每行一个 {query, expected_source_ids, description})。"""
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
            items.append(item)
    logger.info("[eval_rag] 加载 golden set %d 条", len(items))
    return items


def recall_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    """Recall@K:top-K 命中 expected 的比例。"""
    if not expected_ids:
        return 0.0
    top_k_set = set(retrieved_ids[:k])
    hit = len(top_k_set & set(expected_ids))
    return hit / len(set(expected_ids))


def mrr(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    """MRR:第一个命中 expected 的 rank 的倒数;无命中返回 0。"""
    expected = set(expected_ids)
    for i, sid in enumerate(retrieved_ids, start=1):
        if sid in expected:
            return 1.0 / i
    return 0.0


def eval_method(
    method: str,
    query: str,
    top_k: int,
) -> list[str]:
    """跑单种检索方法,返回 source_id 列表。

    method: 'bm25' / 'vector' / 'rrf'
    """
    if method == "bm25":
        evs = bm25_search(query, top_k=top_k)
        return [e.source_id for e in evs]
    if method == "vector":
        emb = embed_query(query)
        evs = knn_search(emb, top_k=top_k)
        return [e.source_id for e in evs]
    if method == "rrf":
        pack = retrieve(query, top_k=top_k)
        return pack.source_ids
    raise ValueError(f"未知 method: {method}")


def run_eval(top_k: int = 10) -> dict:
    """跑全量评估,返回 {method: {recall@5, recall@10, mrr}}。"""
    golden = load_golden_set()
    methods = ["bm25", "vector", "rrf"]
    results: dict[str, dict[str, float]] = {
        m: {"recall@5": 0.0, "recall@10": 0.0, "mrr": 0.0, "count": 0}
        for m in methods
    }

    for item in golden:
        query = item["query"]
        expected = item["expected_source_ids"]
        for m in methods:
            try:
                retrieved = eval_method(m, query, top_k=top_k)
            except Exception as e:
                logger.warning(
                    "[eval_rag] method=%s query=%s 失败: %s: %s",
                    m, query[:40], type(e).__name__, e,
                )
                continue
            results[m]["recall@5"] += recall_at_k(retrieved, expected, 5)
            results[m]["recall@10"] += recall_at_k(retrieved, expected, 10)
            results[m]["mrr"] += mrr(retrieved, expected)
            results[m]["count"] += 1

    # 取平均
    n = len(golden) or 1
    for m in methods:
        c = results[m]["count"] or 1
        # 按成功次数平均(失败的 query 不计入分母)
        results[m]["recall@5"] = results[m]["recall@5"] / c
        results[m]["recall@10"] = results[m]["recall@10"] / c
        results[m]["mrr"] = results[m]["mrr"] / c
    return results


def format_report(results: dict, top_k: int) -> str:
    """生成 Markdown 报告。"""
    lines = [
        "# RAG 检索评估报告",
        "",
        f"生成时间: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"top_k 参数: {top_k}",
        "",
        "| Method | Recall@5 | Recall@10 | MRR | 成功 query 数 |",
        "|---|---|---|---|---|",
    ]
    for m in ["bm25", "vector", "rrf"]:
        r = results[m]
        lines.append(
            f"| {m} | {r['recall@5']:.4f} | {r['recall@10']:.4f} | {r['mrr']:.4f} | {int(r['count'])} |"
        )
    lines.extend([
        "",
        "## 指标说明",
        "- Recall@K: top-K 命中 expected_source_ids 的比例",
        "- MRR: 第一个命中 expected 的 rank 倒数均值",
        "",
        "## 解读指引",
        "- RRF 应在 Recall@K 上不弱于两路单路(融合优势)",
        "- BM25 强在字段精确(attack_type / IP),Vector 弱在这些场景",
        "- Vector 强在语义查询(同义词/中英文混合),BM25 弱在这些场景",
        "- 若 RRF 全面低于单路,检查 RRF k 参数或 candidate_k 倍数",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="RAG 检索离线评估")
    parser.add_argument("--top_k", type=int, default=10, help="检索候选数(默认 10)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    logger.info("[eval_rag] 开始评估 top_k=%d", args.top_k)
    results = run_eval(top_k=args.top_k)
    report = format_report(results, args.top_k)

    # 打印到 stdout
    print(report)

    # 写入 evals/report_rag_{timestamp}.md
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"report_rag_{ts}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("[eval_rag] 报告已写入: %s", report_path)


if __name__ == "__main__":
    main()
