"""Read the rule-engine application YAML without coupling it to engine rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Settings:
    profile_path: Path
    regex_path: Path
    bootstrap_servers: list[str]
    consumer_topic: str
    consumer_group_id: str
    auto_offset_reset: str
    enable_auto_commit: bool
    producer_topics: list[str]


def load_settings(config_path: str | Path | None = None) -> Settings:
    service_root = Path(__file__).resolve().parents[1]
    path = Path(config_path) if config_path else service_root / "config" / "app.licationyaml"
    with path.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = yaml.safe_load(file) or {}

    rule = data.get("rule", {})
    kafka = data.get("kafka", {})
    consumer = kafka.get("consumer", {})
    producer = kafka.get("producer", {})
    return Settings(
        profile_path=(service_root / rule.get("profile_path", "rules/profiles")).resolve(),
        regex_path=(service_root / rule.get("regex_path", "rules/regex")).resolve(),
        bootstrap_servers=list(kafka.get("bootstrap_servers", ["localhost:9092"])),
        consumer_topic=str(consumer.get("topic", "log.structured")),
        consumer_group_id=str(consumer.get("group_id", "rule-engine-group")),
        auto_offset_reset=str(consumer.get("auto_offset_reset", "latest")),
        enable_auto_commit=bool(consumer.get("enable_auto_commit", False)),
        producer_topics=list(producer.get("topics", ["log.analysis"])),
    )
