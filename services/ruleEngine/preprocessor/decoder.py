"""Safe, repeatable decoding of string fields in a raw log."""

from __future__ import annotations

import codecs
import html
from typing import Any, Mapping
from urllib.parse import unquote


class Decoder:
    """Decodes URL, HTML entity, and unicode-escape representations.

    URL decoding is applied until it stabilizes (up to ``max_url_decodes``), so a
    doubly encoded payload is normalized while malformed percent escapes remain
    harmless text.
    """

    def __init__(self, max_url_decodes: int = 2) -> None:
        self.max_url_decodes = max_url_decodes

    def decode_value(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        decoded = value
        for _ in range(self.max_url_decodes):
            next_value = unquote(decoded)
            if next_value == decoded:
                break
            decoded = next_value
        decoded = html.unescape(decoded)
        return self._decode_unicode_escapes(decoded)

    @staticmethod
    def _decode_unicode_escapes(value: str) -> str:
        # Only process explicit escape sequences.  Decoding an arbitrary Unicode
        # string with ``unicode_escape`` would corrupt non-ASCII log content.
        if "\\u" not in value and "\\U" not in value and "\\x" not in value:
            return value
        try:
            return codecs.decode(value, "unicode_escape")
        except UnicodeDecodeError:
            return value

    def decode(self, raw_log: Mapping[str, Any]) -> dict[str, Any]:
        return {key: self.decode_value(value) for key, value in raw_log.items()}
