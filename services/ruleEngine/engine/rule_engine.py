"""Rule-profile driven detection engine."""

from __future__ import annotations

from typing import Any

from ..models.log_message import LogMessage
from ..models.security_event import Detection, SecurityEvent
from .event_builder import EventBuilder
from .regex_matcher import RegexMatcher
from .rule_loader import LoadedRules, RuleLoader


class RuleEngine:
    def __init__(self, rule_loader: RuleLoader, regex_matcher: RegexMatcher | None = None,
                 event_builder: EventBuilder | None = None) -> None:
        self.rule_loader = rule_loader
        self.regex_matcher = regex_matcher or RegexMatcher()
        self.event_builder = event_builder or EventBuilder()
        self._rules: LoadedRules | None = None

    def reload(self) -> None:
        self._rules = self.rule_loader.load()

    def analyze(self, log: LogMessage) -> SecurityEvent | None:
        rules = self._rules or self._load_rules()
        detections: list[Detection] = []
        for profile in rules.profiles:
            if not profile.get("enabled", True):
                continue
            matches = []
            for matcher in profile["matchers"]:
                library = rules.libraries[matcher["library"]]
                for field in profile["target_fields"]:
                    matches.extend(self.regex_matcher.match(field, log.get_field(field), library["patterns"]))
            if matches:
                detections.append(Detection(
                    rule_id=profile["id"],
                    attack_type=str(profile.get("attack_type", profile["id"])),
                    matches=tuple(matches),
                ))
        return self.event_builder.build(log, detections) if detections else None

    def _load_rules(self) -> LoadedRules:
        self._rules = self.rule_loader.load()
        return self._rules
