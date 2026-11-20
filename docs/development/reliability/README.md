# Reliability

| Topic | Reference | Implementation |
| --- | --- | --- |
| Retry | [Usage](retry/usage.md), [design](retry/design.md) | [Retry module](../../../core/stable/retry/) |
| Circuit breaking | [Design](circuit-breaker/design.md) | [Circuit-breaker module](../../../core/stable/circuit_breaker/) |
| Dead-letter queues | [Overview](dlq/overview.md), [historical alignment analysis](dlq/alignment.md) | [DLQ producer](../../../core/kafka/dlq.py) |
| Worker integration | [Agent stability](../agent/stability-strategy.md) | [Analysis worker](../../../services/agent/main.py) |

Retry integration and component usage serve different purposes and stay separate. The alignment document describes the pre-alignment problem and proposal; the DLQ overview describes the subsequent implementation snapshot. Do not interpret old proposal sections as outstanding changes without checking the source.

Historical pass counts in retained documents are records from their authoring dates, not a claim that tests were rerun during documentation organization. Private `devtools/` scripts mentioned in older notes are not part of a fresh clone.
