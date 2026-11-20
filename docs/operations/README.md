# Operations

Use the [root setup guide](../../README.md) and the [.env.example](../../.env.example) configuration template for this checkout. Keep actual environment values local.

- [Docker operations](docker.md): Compose commands, persistence boundaries, and configuration ownership.
- [DLQ reference](../development/reliability/dlq/overview.md): producer fields and downstream routing.
- [Agent failure handling](../development/agent/stability-strategy.md): retries, circuit breaking, and degraded results.

Detailed security reviews, deployment-specific findings, backup evidence, and migration approvals are private records under `document/reviews/` or `document/plans/`, not public runbooks. Never execute an archived migration plan without a fresh review of the target deployment.
