"""Entrypoint for the rule engine service.

Run from the repository root with ``python -m services.ruleEngine.main``.
"""

import logging

from .config.settings import load_settings
from .engine.rule_engine import RuleEngine
from .engine.rule_loader import RuleLoader
from .kafka.kafka_consumer import KafkaConsumerAdapter
from .kafka.kafka_producer import KafkaProducerAdapter, DlqProducer
from .pipeline.analysis_pipeline import AnalysisPipeline
from .preprocessor.preprocessor import Preprocessor
from .preprocessor.structure_normalizer import LogValidationError


def build_pipeline() -> AnalysisPipeline:
    settings = load_settings()
    return AnalysisPipeline(
        preprocessor=Preprocessor(),
        rule_engine=RuleEngine(RuleLoader(settings.profile_path, settings.regex_path)),
    )


def main() -> None:
    settings = load_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger = logging.getLogger("rule_engine")
    pipeline = build_pipeline()
    consumer = KafkaConsumerAdapter(
        settings.bootstrap_servers, settings.consumer_topic, settings.consumer_group_id,
        settings.auto_offset_reset, settings.enable_auto_commit,
    )
    producer = KafkaProducerAdapter(settings.bootstrap_servers, settings.producer_topics)
    dlq_producer = DlqProducer(settings.bootstrap_servers, settings.dlq_topic)
    consumer.connect()
    producer.connect()
    dlq_producer.connect()
    producer.set_consumer(consumer)
    logger.info("Rule engine started: %s -> %s, dlq: %s",
                settings.consumer_topic, settings.producer_topics, settings.dlq_topic)
    try:
        for raw_log in consumer.consume():
            try:
                event = pipeline.process(raw_log)
            except LogValidationError as error:
                logger.warning("Sending invalid log to DLQ: %s", error)
                dlq_producer.send(raw_log if isinstance(raw_log, dict) else raw_log)
                producer.commit_offset()
                continue
            except Exception as error:
                logger.error("Error processing log message, sending to DLQ: %s", error, exc_info=True)
                dlq_producer.send(raw_log if isinstance(raw_log, dict) else raw_log)
                producer.commit_offset()
                continue
            if event is not None:
                producer.send(event)
            else:
                producer.commit_offset()
    finally:
        consumer.close()
        producer.close()
        dlq_producer.close()


if __name__ == "__main__":
    main()
