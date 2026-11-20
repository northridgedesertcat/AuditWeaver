# Development Reference

| Component | Documentation | Source |
| --- | --- | --- |
| Web platform | [API and request-flow index](web/README.md) | [Website](../../services/website/) |
| Agent service | [Workflows and investigation agents](agent-service/README.md) | [Agent service](../../services/agent_service/) |
| Analysis worker | [Stability strategy](agent/stability-strategy.md), [retry integration](agent/retry-strategy.md) | [Agent worker](../../services/agent/) |
| Rule engine | [Design and data contracts](rule-engine/README.md) | [Rule engine](../../services/ruleEngine/) |
| Shared reliability | [Retry, circuit breakers, and DLQ](reliability/README.md) | [Stability primitives](../../core/stable/), [Kafka utilities](../../core/kafka/) |
| Time handling | [Time conventions and caveats](time.md) | [Python time helpers](../../common/time_utils.py) |

These are reference documents, not a second installation guide. Follow the root [README](../../README.md) and the configuration template for this checkout. Retained design documents may describe the state at their original authoring date; verify behavior against source before changing code or a deployment.
