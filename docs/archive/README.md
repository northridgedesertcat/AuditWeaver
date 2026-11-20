# Documentation Archive

These documents describe earlier designs, proposals, or implementation snapshots. They are preserved for context, not validated current operating procedures. Old bug lists do not establish whether a defect remains open. Removed implementation paths are rendered as historical text rather than misleading links to unrelated current code.

## Legacy Pipeline

- [Bug notebook](legacy/bugs.md).
- [Data-flow structures](legacy/data-flow.md): the earlier LogSentinel / `rulesMatching` / ES-report pipeline.
- [Rule-module strategy](legacy/rule-module-strategy.md): the predecessor of the current rule engine.

For maintained entry points, use the [web reference](../development/web/README.md), [rule engine](../development/rule-engine/README.md), and [agent service](../development/agent-service/README.md).

## Time Refactor

- [Original analysis](time-system/analysis.md).
- [Implementation plan](time-system/plan.md).
- [Specification](time-system/specification.md).

Their overlapping guidance is consolidated into the active [time-handling reference](../development/time.md). The originals remain separate to preserve the analysis and decisions rather than erase provenance.

## Architecture History

- [V0](architecture/v0.png), [V0.1](architecture/v0.1.png), [V1](architecture/v1.png).
- [Planned V2](architecture/planned-v2.png): proposal, not a statement of the deployed system.
- [Pre-storage platform drawing](architecture/pre-hot-cold/platform.drawio), [its PNG](architecture/pre-hot-cold/platform.png), and [an older detailed system export](architecture/pre-hot-cold/system-detail.png): retained snapshots that predate the hot/cold storage diagrams. The detailed PNG has no verified source/export pairing.

Editable historical drawing sources and alternate private exports remain local under `document/archive/design/`. The retained public PNGs are not claimed to reproduce those sources exactly.
