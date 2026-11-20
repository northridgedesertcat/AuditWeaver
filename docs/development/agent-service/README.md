# Agent Service

The internal FastAPI service hosts two LangGraph applications. It is separate from the Kafka analysis worker in `services/agent/`. The web platform proxies requests through Django; see the [web authentication and proxy reference](../web/auth-and-middleware.md).

## Workflow and Investigation

| Application | Flow | Implementation |
| --- | --- | --- |
| `analysis_workflow` | Retrieve evidence, analyze, validate, optionally enrich, then report | [Workflow graph](../../../services/agent_service/agents/workflow/analysis_workflow/graph.py) |
| `analysis_explorer` | Plan, run a ReAct/tool loop, evaluate a deterministic gate, then continue, replan, compact, or finish | [Explorer graph](../../../services/agent_service/agents/react/analysis_explorer/graph.py) |

The workflow bounds enrichment using `MAX_ENRICH_COUNT` and routes to report generation when validation is unavailable or the enrichment budget is exhausted. This is not proof that the report passed validation. Its graph compiles without a checkpointer in this baseline.

The explorer checks the deterministic gate after tool execution. Only a triggered gate invokes the decision model. The graph compiles with the shared checkpointer; deployment configuration determines the memory backend. An ordinary model response with no tool calls can also end the investigation.

## Diagrams

- [Current Agent and storage architecture](../../architecture/README.md): updated evidence access through the shared query service, ClickHouse archive, and outbox-driven RAG synchronization.
- [Workflow source](diagrams/analysis-workflow.mmd) and [existing workflow export](diagrams/analysis-workflow.png).
- [Explorer source](diagrams/analysis-explorer.mmd) and [existing explorer export](diagrams/analysis-explorer.png).
- [Exploration drawing](diagrams/exploration.drawio): an originally untitled working diagram, retained as a draft. It is not asserted to be the source of either export above.

The component exports above are retained snapshots. The current architecture guide maintains separate source/export pairs for the complete system and its storage dependencies.

## Ownership

| Concern | Source |
| --- | --- |
| FastAPI lifecycle and background case synchronization | [Backend entry point](../../../services/agent_service/backend/main.py) |
| HTTP and SSE routes | [Routes](../../../services/agent_service/backend/routes/) |
| Retrieval and case synchronization | [Shared RAG module](../../../services/agent_service/shared/rag/) |
| Memory backend | [Shared memory](../../../services/agent_service/shared/memory/) |
| MCP tools | [Skills](../../../services/agent_service/skills/) |
| Evaluation | [Evaluation guide](../../evaluation/README.md) |

Detailed implementation proposals and personal walkthroughs remain local under `document/plans/agent-service/`. They are not a second source of operational requirements.
