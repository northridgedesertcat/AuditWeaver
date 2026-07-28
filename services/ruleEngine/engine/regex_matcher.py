"""Regex matching implementation for rule profiles."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from ..models.security_event import MatchResult


class RegexMatcher:
    """Applies enabled regex definitions and returns forensic match details."""

    def match(self, field: str, value: Any,
              patterns: Iterable[Mapping[str, Any]]) -> list[MatchResult]:
        if not isinstance(value, str) or not value:
            return []

        results: list[MatchResult] = []
        for pattern in patterns:
            if not pattern.get("enabled", True):
                continue
            pattern_id = pattern.get("id")
            expression = pattern.get("regex")
            if not isinstance(pattern_id, str) or not isinstance(expression, str):
                continue
            try:
                if re.search(expression, value):
                    # The complete normalized field is retained for investigation;
                    # pattern_id identifies the exact matching expression.
                    results.append(MatchResult(field, pattern_id, value))
            except re.error as error:
                raise ValueError(f"Invalid regex for pattern '{pattern_id}': {error}") from error
        return results
