# Evaluation

Evaluation code and golden sets stay beside the agent service. This guide consolidates the shared evaluation overview; personal interview explanations remain local. No evaluation was rerun as part of the documentation cleanup.

## Two Evaluation Tracks

| Track | Inputs and Code | Measures |
| --- | --- | --- |
| RAG retrieval | [RAG golden set](../../services/agent_service/evals/golden_set_rag.jsonl), [evaluator](../../services/agent_service/evals/eval_rag.py) | Recall@K, MRR, self-reference rate; BM25, vector, and RRF; case/knowledge buckets |
| Agent investigation | [Agent golden set](../../services/agent_service/evals/golden_set_agent.jsonl), [runner](../../services/agent_service/evals/run_eval.py) | Correctness, evidence coverage, tool recall, wasted calls, completion steps, finish/replan/compact behavior |

The checked-in sets contain 27 retrieval examples and 31 investigation examples. Count the actual fixtures after editing them rather than relying on older script comments. [Metrics](../../services/agent_service/evals/metrics.py) are deterministic functions; the optional [LLM judge](../../services/agent_service/evals/llm_judge.py) provides a separate subjective assessment.

The agent runner compares a baseline two-node ReAct graph with the upgraded graph while reusing the core agent/tool implementation. A failed evaluation or missing judge score must stay visible; never substitute invented numbers.

## Recorded RAG Results

The reviewed [baseline report](reports/rag/2026-09-21/baseline.md) and [after report](reports/rag/2026-09-21/after.md) were generated on September 21, 2026. They are moved evidence files, not newly reproduced measurements.

| RRF Metric | Baseline | After |
| --- | --- | --- |
| Recall@5 | 0.2395 | 0.8556 |
| Recall@10 | 0.3389 | 0.9543 |
| MRR | 0.2531 | 0.9691 |
| Top-5 self-reference rate | 1.0000 | 0.0000 |

The baseline used `exclude_self=False`; the later run used `exclude_self=True`. Corpus content and retrieval behavior also changed. This is a before/after system comparison, not an isolated hyperparameter experiment or a production-scale accuracy claim. The small golden set is suitable for regression signals, not broad generalization guarantees.

The source reports attribute the baseline's zero vector scores to the old kNN query behavior, and report improvements after knowledge-corpus creation, self-reference exclusion, and retrieval fixes. Read their per-bucket tables and caveats before citing the summary numbers.

There is no checked-in full agent-run result corresponding to this baseline. Do not infer agent performance from the retrieval reports.

## Run Deliberately

These commands require configured Elasticsearch, an appropriate corpus, and, for agent runs, a reachable LLM. They can make external requests and incur model costs. Run from the repository root against an approved test environment:

```shell
python -m services.agent_service.evals.eval_rag --label baseline
python -m services.agent_service.evals.eval_rag --label after --exclude-self
python -m services.agent_service.evals.run_eval --variant upgraded --limit 5
python -m services.agent_service.evals.run_eval --variant both --judge
```

Both scripts still write to `services/agent_service/evals/`. Generated `report_*.md` and `results_*.jsonl` files are now ignored. This organization does not change output paths or runtime behavior. Review and sanitize any result before publishing a dated snapshot here, recording its revision, dataset/corpus identity, configuration, and limitations.

## Other Evidence

The [legacy Isolation Forest charts](reports/isolation-forest/README.md) are retained for traceability, but lack enough provenance to support reproducibility or benchmark claims. Future trainer output at its original path remains local.
