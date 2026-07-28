"""Preprocessing facade used by the analysis pipeline."""

from typing import Any, Mapping

from ..models.log_message import LogMessage
from ..models.raw_log import RawLog
from .decoder import Decoder
from .structure_normalizer import StructureNormalizer


class Preprocessor:
    def __init__(self, decoder: Decoder | None = None,
                 normalizer: StructureNormalizer | None = None) -> None:
        self.decoder = decoder or Decoder()
        self.normalizer = normalizer or StructureNormalizer()

    def process(self, raw_log: RawLog | Mapping[str, Any]) -> LogMessage:
        payload = raw_log.payload if isinstance(raw_log, RawLog) else raw_log
        if not isinstance(payload, Mapping):
            raise TypeError("Raw log must be a mapping")
        return self.normalizer.normalize(self.decoder.decode(payload), original_data=payload)
