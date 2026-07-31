# Changelog

## v1.0.0 (2026-08-01)

### Major Changes

#### Rule Engine Restructure
- Rebuild rule matching module as `ruleEngine`. Decouple rule profile repository and regex repository into separate YAML files under `rules/profiles/` and `rules/regex/`.
- Add decode function in preprocessor to support URL-decoded log analysis.
- Support producing matched results to multiple Kafka topics simultaneously.
- Update regex repository with more comprehensive attack patterns.

#### Kafka & Data Pipeline Redesign
- Disable Kafka auto topic creation. All business topics are now explicitly defined in `docker/config/kafka/topics/topics.yaml` and created via `create-init-topics.py`.
- Add `agent.event.save` and `rule.event.save` Kafka topics for structured event persistence.
- Introduce Kafka Connect Elasticsearch Sink connectors for upsert-based event storage. Connector configs stored in `docker/config/kafka-connect/connectors/`.
- Add `init-connectors.py` to automatically initialize Kafka Connect connectors on startup.
- Logstash role shifted to pure data processing; Kafka Connect handles all Elasticsearch write operations.

#### Agent Module Optimization
- Extract YAML configuration files from Python code (`agent.yaml`, `dify_request.yaml`, `extraction_rules.yaml`).
- Consolidate data transformation logic into `preprocessor/` directory with proper module exports.
- Remove direct Elasticsearch dependency. Analysis results now sent to Kafka topic `agent.event.save` for Kafka Connect Sink to handle ES upsert.
- Add Kafka consumer support for receiving structured log data.
- Rename `kafka/` directory to `broker/` to avoid namespace conflict with kafka-python library.

#### Elasticsearch Mapping Decoupling
- Extract ES index mapping definitions from Python scripts into standalone YAML files under `docker/config/elasticsearch/mappings/`.
- Updated `matched_logs.yaml` mapping to align with the new rule engine data model.

#### One-Click Startup
- Add `start.py` Python script with full service orchestration: Docker Compose startup, health checks for ES/Kafka/Kafka Connect, topic initialization, connector initialization, and sequential microservice launching.
- Migrate port, Kafka topic, and ES index configurations to `.env` environment variables for unified management.

#### Architecture & Documentation
- Upgrade system architecture diagram to reflect the new event-driven pipeline.
- Add development documentation for rule engine design, data flow, and architecture decisions.

#### Bug Fixes
- Fix kafka-python 2.x API compatibility issue with `KafkaConsumer` and `KafkaProducer` initialization parameters.
- Fix risk color display abnormality on the frontend dashboard.
- Fix duplicate analysis reports caused by a single log matching multiple rules triggering multiple Dify workflow calls.

## v0.2.0 (2026-07-015)
- add rag function to the agent,update the dify workflow.
- fixed bug: rulematching module would send one log to dify workflow multiple times if it matched multiple rules.

## v0.1.0 (2026-07-12)
- Initial release.
- rename the project to AuditWeaver
- fixed some absolute path issues
