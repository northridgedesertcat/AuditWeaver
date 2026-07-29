"""Preprocessing facade used by the analysis pipeline."""

import logging
from typing import Any, Mapping

from ..models.log_message import LogMessage
from ..models.raw_log import RawLog
from .decoder import Decoder
from .structure_normalizer import StructureNormalizer

logger = logging.getLogger(__name__)


class Preprocessor:
    def __init__(self, decoder: Decoder | None = None,
                 normalizer: StructureNormalizer | None = None) -> None:
        self.decoder = decoder or Decoder()
        self.normalizer = normalizer or StructureNormalizer()

    def process(self, raw_log: RawLog | Mapping[str, Any]) -> LogMessage:
        payload = raw_log.payload if isinstance(raw_log, RawLog) else raw_log
        if not isinstance(payload, Mapping):
            raise TypeError("Raw log must be a mapping")
        decoded = self.decoder.decode(payload)
        result = self.normalizer.normalize(decoded, original_data=payload)
        logger.info("Preprocessed log: event_id=%s, method=%s, path=%s",
                     result.event_id, result.method, result.path)
        return result
