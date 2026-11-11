# RAG 检索评估报告

生成时间: 2026-09-21T22:31:10
标签: baseline
top_k 参数: 10
自引用排除: exclude_self=False(改造前基线行为)

## 总体指标

| Method | Recall@5 | Recall@10 | MRR | 成功 query 数 | 自引用率(top-5) |
|---|---|---|---|---|---|
| bm25 | 0.2395 | 0.3389 | 0.2531 | 27 | 1.0000 |
| vector | 0.0000 | 0.0000 | 0.0000 | 27 | 0.0000 |
| rrf | 0.2395 | 0.3389 | 0.2531 | 27 | 1.0000 |

## 分桶指标(case / knowledge)

### case 查询

| Method | Recall@5 | Recall@10 | MRR | 成功 query 数 |
|---|---|---|---|---|
| bm25 | 0.5389 | 0.7625 | 0.5694 | 12 |
| vector | 0.0000 | 0.0000 | 0.0000 | 12 |
| rrf | 0.5389 | 0.7625 | 0.5694 | 12 |

### knowledge 查询

| Method | Recall@5 | Recall@10 | MRR | 成功 query 数 |
|---|---|---|---|---|
| bm25 | 0.0000 | 0.0000 | 0.0000 | 15 |
| vector | 0.0000 | 0.0000 | 0.0000 | 15 |
| rrf | 0.0000 | 0.0000 | 0.0000 | 15 |

## 指标说明
- Recall@K: top-K 命中 expected_source_ids 的比例(expected 以 '::' 结尾为 doc 级前缀匹配)
- MRR: 第一个命中 expected 的 rank 倒数均值
- 自引用率: 带 self_event_id 的 case 条目中,top-5 结果含自身的比例(改造前应 > 0;P0-2 exclude_ids 后应为 0)

## 解读指引
- RRF 应在 Recall@K 上不弱于两路单路(融合优势)
- BM25 强在字段精确(attack_type / IP),Vector 弱在这些场景
- knowledge 桶:基线(无知识语料)应为 0,知识库落地后 Recall@5 目标 ≥ 0.8
- case 桶:自引用率基线应显著 > 0,改造后(exclude_self)应为 0 且 Recall 不劣化(±2%)