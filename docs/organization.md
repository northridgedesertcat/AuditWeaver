# Documentation Organization Record

Organized on November 12, 2026, on `docs/organize-docs`, based on `origin/develop` at `6b7cb5b`. No application behavior, deployment data, evaluator output paths, or runtime knowledge resources were changed.

## Resulting Layout

```text
README.md / README.zh-CN.md   Project entry points
CHANGELOG.md / LICENSE       Release history and license
docs/
  README.md                  Shared documentation hub
  architecture/diagrams/     System sources and distinct exports
  development/               Component references and time conventions
    agent/
    agent-service/diagrams/
    reliability/
    rule-engine/diagrams/
    web/
  operations/                Safe operational guidance
  evaluation/reports/        Methods and selected historical evidence
  assets/screenshots/        Product screenshots
  archive/                   Superseded designs and old architectures
  contributing.md            Git/local ownership and maintenance rules
  organization.md            This record
document/                    Local-only, entirely ignored by Git
  plans/                     Draft plans and technical walkthroughs
  reviews/                   Security and deployment-specific reviews
  personal/                  Career, study, and interview material
  artifacts/                 Recordings and local captures
  archive/                   Old code, designs, and original draft notes
  organization/              Local move manifest and worktree inventory
```

## Keep in Git

Shared contracts, operational procedures, source-linked component references, editable diagrams, sanitized screenshots, and selected benchmark evidence remain reviewable in Git. Test fixtures, prompts, workflow resources, and RAG knowledge stay at their implementation-owned locations: moving them as if they were ordinary prose would change the application.

| Previous Location | Current Location / Decision |
| --- | --- |
| `docs/develop/agent/` | `docs/development/agent/`, with kebab-case filenames |
| `docs/develop/agent_service/` | `docs/development/agent-service/diagrams/`, plus an English component index |
| `docs/develop/ruleEngine/` | `docs/development/rule-engine/`, descriptive diagram filenames |
| `docs/develop/stable/retry/` | `docs/development/reliability/retry/` |
| `docs/develop/stable/circuit_breaker/` | `docs/development/reliability/circuit-breaker/` |
| `docs/develop/stable/dlq/` | `docs/development/reliability/dlq/`; `alingment.md` corrected to `alignment.md` |
| `docs/develop/web/` | `docs/development/web/`, retaining its API/auth/frontend/schema split |
| `docs/develop/system-design/feature-architecture/` | `docs/architecture/diagrams/`; sources and distinct exports preserved |
| `docs/images/Current.png`, `Current_simple.png` | `docs/architecture/diagrams/system.png`, `system-simple.png` |
| `docs/images/dashboard.png`, `report1.png`, `report2.png` | `docs/assets/screenshots/`, descriptive kebab-case names |
| `docs/images/version.png`, `docs/history/` | `docs/archive/architecture/`; V2 explicitly labeled as a proposal |
| `services/agent_service/evals/report_rag_baseline_20260921_223110.md` | `docs/evaluation/reports/rag/2026-09-21/baseline.md` |
| `services/agent_service/evals/report_rag_after_20260921_224305.md` | `docs/evaluation/reports/rag/2026-09-21/after.md` |
| `services/isolationForest/trainer/evaluation_results/*.png` | `docs/evaluation/reports/isolation-forest/legacy/`, with a provenance warning |

The previously untracked, unnamed agent-service drawing was preserved as `exploration.drawio` and labeled a draft. It is included in the proposed shared changes, not silently discarded or claimed to match another export.

## Keep Locally

| Previous Category | Local Destination | Reason |
| --- | --- | --- |
| `document/develop/` | `document/plans/` | Plans include outdated assumptions and branch-specific decisions; publish condensed, reviewed guidance instead of every working conversation. |
| Production-readiness review | `document/reviews/` | Deployment-sensitive and time-bound assessment, not current certification. |
| `document/security/` | `document/reviews/security/` | Vulnerability details and environment findings require explicit disclosure review. |
| `document/myself/` | `document/personal/career/` | Resumes, job descriptions, and personal project narratives are not repository reference docs. |
| `document/selfdoc/` | `document/personal/study/` | Interview/study explanations serve a different audience from contributor guides. |
| `document/simulateInterview/` | `document/personal/interviews/` | Personal preparation, not public technical requirements. |
| `document/design/demo/show.mp4` | `document/artifacts/demos/` | Large local recording; not needed to build or maintain the project. |
| `document/design/` | `document/archive/design/` | Unique old diagram sources and alternate exports preserved locally. |
| `document/old version/` | `document/archive/legacy-code/` | Old source, cached bytecode, and sample logs are not shared documentation. |

Every unique local file was preserved. The local `document/organization/moves.csv` records 1,646 per-file actions and original SHA256 values; it is intentionally not published because it inventories private material. A separate local record lists documents found in sibling worktrees. Those worktrees were not modified, including storage preview helpers that depend on their existing paths.

Git ignore rules are not a backup system. Preserve ignored notes and artifacts using a private backup before removing worktrees or replacing a computer.

## Consolidate and Archive

- The previously untracked `docs/eval/README.md` and the private evaluation study guide overlapped. Shared methodology, commands, measured results, and comparison caveats are consolidated into the English [evaluation guide](evaluation/README.md); the original draft and personal study version remain local.
- The one-line `docker/upCommand.txt` is covered by [Docker operations](operations/docker.md); its original copy remains in the local documentation archive.
- Three overlapping time-analysis/refactor documents are preserved in `docs/archive/time-system/`. The active [time reference](development/time.md) summarizes existing behavior and calls out compatibility pitfalls rather than presenting old plans as current instructions.
- Earlier LogSentinel / `rulesMatching` data flow, rule strategy, and bug notes are preserved under `docs/archive/legacy/`, with a clear historical entry point.
- Private agent walkthroughs were not published wholesale. The new [agent-service index](development/agent-service/README.md) provides a concise source-linked explanation of both graphs.
- Retry usage, retry design, and worker integration remain separate because they answer different questions. Web API, auth, frontend usage, and schema references also remain separate.

## Remove Verified Redundancy

| Removed Copy | Retained Content |
| --- | --- |
| `ai Architecture/Agent Service Event.png` | Byte-identical `docs/architecture/diagrams/system.png` |
| `ai Architecture/Untitled diagram-2026-09-12-073825.png` | Byte-identical `docs/architecture/diagrams/system-simple.png` |
| `document/design/v2/version.png` | Byte-identical `docs/archive/architecture/planned-v2.png` |
| Empty `docs/develop/docker/elasticsearch.md` | Replaced by indexed [Docker guidance](operations/docker.md) and links to ES configuration |
| Empty `docs/develop/ruleEngine/prompts.md` | No content to retain; actual runtime configuration is untouched |

No unique design, personal note, old code snapshot, sample log, or security review was deleted. Bytecode caches, editor backups, generated sample data, and old recordings remain candidates for a separate cleanup after their backup and retention needs are confirmed.

## Validation and Limits

Portable relative links replace machine-specific `file:///` paths. Links to removed implementations are labeled as historical text, and shared docs no longer require ignored private files. Future generated evaluation reports and results are ignored at their current output paths; golden sets and evaluators remain tracked.

Run `python scripts/check_docs.py` and the checker regression tests described in [the policy](contributing.md). The check covers local Markdown destinations, not external URLs, heading fragments, API semantics, or diagram/export equivalence. Archived benchmarks were not rerun and do not establish current system performance.

This branch deliberately does not merge newer application commits from `main`. When integrating with `main`, retain its existing `docs/development.md` launcher guide and `services/log_storage/README.md`, linking them from the hub rather than duplicating their contents.

## Architecture Follow-up

At the user's request, the maintained architecture diagrams now reflect the implemented hot/cold storage on `main` at `51508a3`. The diagrams use English labels, with focused storage and Agent views. This is an intentional content update beyond the original preservation-only moves. The old platform drawing, its PNG, and the unmatched detailed PNG are retained under `docs/archive/architecture/pre-hot-cold/`. No runtime code was imported or enabled.

On November 13, 2026, the root READMEs and architecture guide were updated to lead with one connected system diagram: log sources, Kafka/Logstash, rule detection, storage workers, Dify analysis, Elasticsearch/ClickHouse/MySQL/Redis, shared queries, the Agent microservice, Django, and Next.js. Its editable source is `system.drawio`, with SVG and high-resolution PNG exports; `system-architecture.mmd` provides a logical companion. The six-area inventory remains an optional reference. Historical V2 images are linked from the archive instead of appearing inline beside the current architecture.
