# Editing Architecture Diagrams

PNGs serve the root READMEs; SVGs allow readers to zoom without losing text quality. Keep editable sources and both export formats together.

## Overall Presentation

`system.drawio` is the editable source for the complete system architecture. Open it in diagrams.net or a compatible editor. It contains individual components, labels, and routed connectors on a 2300 x 1580 canvas. The layout connects sources, processing, the four stores, and analyst applications in one composition.

After editing, export a white-background SVG as `system.svg` and a 2x PNG as `system.png` (4600 x 3160 for the current canvas). Export the complete page, keep Arial, and leave transparent background disabled. Inspect the resulting images because editor versions can differ in text metrics.

`system-architecture.mmd` is a logical companion, not the generator of the presentation exports. Update it when relationships change. Render it under a separate name, such as `system-logical.svg`, when needed; do not overwrite the draw.io presentation with an automatic Mermaid layout.

## Focused Mermaid Views

The following exports use Mermaid CLI **12.2.0**, the shared `mermaid.config.json`, the classic look, Arial, a white background, and PNG scale 2. Rendering does not require starting AuditWeaver or connecting to its databases.

From the repository root:

```shell
npx --yes --package @mermaid-js/mermaid-cli@12.2.0 mmdc -i docs/architecture/diagrams/log-storage.mmd -o docs/architecture/diagrams/log-storage.svg -c docs/architecture/diagrams/mermaid.config.json -b white -I log-storage --no-font-embed
npx --yes --package @mermaid-js/mermaid-cli@12.2.0 mmdc -i docs/architecture/diagrams/log-storage.mmd -o docs/architecture/diagrams/log-storage.png -c docs/architecture/diagrams/mermaid.config.json -b white -I log-storage -s 2
```

Repeat for the following pairs, generating both formats:

| Source | Purpose | Export Basename / SVG ID |
| --- | --- | --- |
| `log-storage.mmd` | Storage internals | `log-storage` |
| `agent-architecture-detail.mmd` | Agent internals | `agent-detail` |
| `system-architecture-simple.mmd` | Optional component inventory | `system-simple` |

Mermaid CLI uses Puppeteer. To use an existing Chrome installation, pass `-p` with a local Puppeteer JSON configuration containing its `executablePath`. Keep that machine-specific configuration and downloaded renderer dependencies outside shared documentation, for example in ignored `document/`. The frontend dependency files do not need to change.

After editing, inspect the exports for overlapping labels, misleading intersections, and clipping. Run `python scripts/check_docs.py`, then stage the source and exports together. The [architecture guide](../README.md) records the implementation revision and distinguishes hybrid mode from deployment defaults.
