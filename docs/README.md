# Documentation

Start with the [project overview](../README.md) for installation and configuration. This directory contains shared project documentation; local working material belongs in the Git-ignored `document/` directory.

## Find a Document

| Topic | Entry Point |
| --- | --- |
| System architecture and editable diagrams | [Architecture](architecture/README.md) |
| Components, source references, and conventions | [Development](development/README.md) |
| Django APIs, authentication, and frontend integration | [Web platform](development/web/README.md) |
| LangGraph workflows, investigation agents, and RAG | [Agent service](development/agent-service/README.md) |
| Kafka analysis worker, retry, and degradation | [Agent stability](development/agent/stability-strategy.md) |
| Rule matching contracts and component design | [Rule engine](development/rule-engine/README.md) |
| Retry, circuit breakers, and dead-letter queues | [Reliability](development/reliability/README.md) |
| Container operations and configuration ownership | [Operations](operations/README.md) |
| Evaluation methods and reviewed historical results | [Evaluation](evaluation/README.md) |
| Superseded designs and version diagrams | [Archive](archive/README.md) |
| What belongs in Git and how to maintain docs | [Documentation policy](contributing.md) |
| Cleanup decisions and old-to-new locations | [Organization record](organization.md) |

## Reading Status

New navigation and maintenance documents are in English. Existing Chinese technical references are preserved, not silently translated or rewritten. Archived documents are historical evidence, not current deployment instructions. Some retained component references predate later implementation changes; the corresponding source code takes precedence.

This organization starts from `develop` at `6b7cb5b`. The architecture diagrams were subsequently updated against the hot/cold storage implementation on `main` at `51508a3`. The newer development launcher guide and log-storage service README on `main` are intentionally not imported with application changes. Keep those guides alongside this structure when the branches are integrated.
