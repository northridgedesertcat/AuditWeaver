# Rule Engine

The [entry point](../../../services/ruleEngine/main.py) builds the preprocessor, rule loader, engine, and analysis pipeline. It consumes structured Kafka logs and publishes detected events. The [profile and regex configuration](../../../services/ruleEngine/config/) remains with the implementation.

| Reference | Purpose |
| --- | --- |
| [Module responsibilities](module-design.md) | Ownership boundaries and inputs/outputs |
| [Class design](class-design.md) | Component responsibilities and collaboration |
| [Data model](data-model.md) | Log and rule contract examples |
| [Editable pipeline diagram](diagrams/rule-match.drawio) | Diagram source |
| [Pipeline export](diagrams/rule-match.png) | Existing visual snapshot |

These designs are retained references, not a replacement for current validation code or tests. The previous `rulesMatching` implementation and its historical data-flow notes are in the [shared archive](../../archive/README.md); its old local source snapshot remains ignored under `document/archive/legacy-code/`.
