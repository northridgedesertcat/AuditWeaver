"""Orchestration layer for a single Kafka log analysis flow."""

from __future__ import annotations

from typing import Any, Mapping

from ..engine.rule_engine import RuleEngine
from ..models.raw_log import RawLog
from ..models.security_event import SecurityEvent
from ..preprocessor.preprocessor import Preprocessor


class AnalysisPipeline:
    def __init__(self, preprocessor: Preprocessor, rule_engine: RuleEngine) -> None:
        self.preprocessor = preprocessor
        self.rule_engine = rule_engine

    def process(self, raw_log: RawLog | Mapping[str, Any]) -> SecurityEvent | None:
        return self.rule_engine.analyze(self.preprocessor.process(raw_log))
