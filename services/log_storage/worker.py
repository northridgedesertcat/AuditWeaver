"""At-least-once storage worker; failures stop consumption without advancing offsets."""
from __future__ import annotations

import base64
import json
import logging
import signal
import time

from common import env
from common.log_query.types import QueryError
from .contract import Source, normalize
from .metadata import DjangoMetadata, topic_for

logger = logging.getLogger(__name__)


def persist_batch(sink, kind, messages, store, metadata, quarantine):
    rows, positions = [], {}
    for msg in messages:
        source = Source(msg.topic(), msg.partition(), msg.offset(), msg.timestamp()[1])
        try:
            payload = json.loads(msg.value())
            row = normalize(kind, payload, source)
            if msg.key() is not None and msg.key() != row["event_id"].encode():
                raise QueryError("Kafka key must equal event_id; repair producer before replay")
            rows.append(row)
            positions[(source.topic, source.partition)] = source.offset + 1
        except (ValueError, TypeError, UnicodeDecodeError, OverflowError) as exc:
            metadata.gap(sink, source, exc)
            quarantine(source, msg.value(), str(exc))
            raise QueryError(f"Quarantined {source}; offsets not committed") from exc
    try:
        store.write(kind, rows)
    except QueryError as exc:
        # Identity conflicts are data errors; retain every original record in this failed batch.
        for msg in messages:
            source = Source(msg.topic(), msg.partition(), msg.offset(), msg.timestamp()[1])
            metadata.gap(sink, source, exc)
            quarantine(source, msg.value(), str(exc))
        raise
    metadata.advance(sink, kind, rows, positions)
    return positions


def run(sink, kind):
    from confluent_kafka import Consumer, Producer, TopicPartition
    from .clickhouse import ClickHouseStore
    from .hot import HotStore
    topic = topic_for(kind)
    group = f"auditweaver-{sink}-{'raw' if kind == 'raw' else 'events'}{'-hot' if sink == 'es' else ''}-v1"
    consumer = Consumer({
        "bootstrap.servers": env.KAFKA_BROKERS, "group.id": group,
        "broker.address.family": env.get_env("STORAGE_KAFKA_ADDRESS_FAMILY", "any"),
        "auto.offset.reset": "earliest", "enable.auto.commit": False, "enable.auto.offset.store": False,
        "max.poll.interval.ms": 300000, "isolation.level": "read_committed",
    })
    producer = Producer({"bootstrap.servers": env.KAFKA_BROKERS, "acks": "all", "enable.idempotence": True,
                         "broker.address.family": env.get_env("STORAGE_KAFKA_ADDRESS_FAMILY", "any")})
    metadata = DjangoMetadata()
    store = ClickHouseStore() if sink == "ck" else HotStore()
    stop = False
    def shutdown(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    def quarantine(source, raw, error):
        errors = []
        value = json.dumps({"source": source.__dict__, "raw_base64": base64.b64encode(raw or b"").decode(), "error": error})
        producer.produce(env.get_env("KAFKA_TOPIC_STORAGE_QUARANTINE", "log.storage.quarantine"),
                         key=f"{sink}:{source.topic}:{source.partition}:{source.offset}", value=value,
                         on_delivery=lambda err, _: errors.append(err) if err else None)
        if producer.flush(30) or errors:
            raise RuntimeError("Quarantine delivery failed; original offset retained")

    def assignment(client, partitions):
        counts = len(client.list_topics(topic, timeout=10).topics[topic].partitions)
        committed = {(p.topic, p.partition): p.offset for p in client.committed(partitions, timeout=10)}
        for p in partitions:
            low, high = client.get_watermark_offsets(p, timeout=10, cached=False)
            prior = committed[(p.topic, p.partition)]
            # Missing commits start at the earliest retained offset, recorded explicitly.
            position = metadata.observe(sink, topic, p.partition, low, high, counts,
                                        initial_offset=low if prior < 0 else prior)
            if prior >= 0 and prior > position:
                raise RuntimeError("Kafka commit is ahead of durable metadata")
            p.offset = low if prior < 0 else prior
            if p.offset < low:
                raise RuntimeError("Kafka retention gap; refusing automatic offset reset")
        client.assign(partitions)

    max_rows = max(1, env.get_env_int("STORAGE_BATCH_ROWS", 5000))
    max_bytes = max(1, env.get_env_int("STORAGE_BATCH_BYTES", 5242880))
    interval = max(0.05, env.get_env_float("STORAGE_FLUSH_INTERVAL_SECONDS", 1))
    batch, size, started, observed = [], 0, time.monotonic(), 0
    def revoked(client, partitions):
        nonlocal batch, size, started
        # Abandon uncommitted buffers and replay them under the next owner.
        batch, size, started = [], 0, time.monotonic()
    consumer.subscribe([topic], on_assign=assignment, on_revoke=revoked, on_lost=revoked)
    try:
        while not stop:
            message = consumer.poll(0.1)
            if message is not None:
                if message.error():
                    raise RuntimeError(message.error())
                byte_count = len(message.value() or b"")
                if byte_count > max_bytes:
                    source = Source(message.topic(), message.partition(), message.offset(), message.timestamp()[1])
                    metadata.gap(sink, source, "Message exceeds STORAGE_BATCH_BYTES")
                    quarantine(source, message.value(), "Message exceeds STORAGE_BATCH_BYTES")
                    raise QueryError("Oversized message; offset retained")
                if batch and size + byte_count > max_bytes:
                    positions = persist_batch(sink, kind, batch, store, metadata, quarantine)
                    consumer.commit(offsets=[TopicPartition(t, p, o) for (t, p), o in positions.items()], asynchronous=False)
                    batch, size, started = [], 0, time.monotonic()
                batch.append(message)
                size += byte_count
            if batch and (len(batch) >= max_rows or time.monotonic() - started >= interval):
                positions = persist_batch(sink, kind, batch, store, metadata, quarantine)
                consumer.commit(offsets=[TopicPartition(t, p, o) for (t, p), o in positions.items()], asynchronous=False)
                batch, size, started = [], 0, time.monotonic()
            if time.monotonic() - observed >= 5:
                counts = len(consumer.list_topics(topic, timeout=10).topics[topic].partitions)
                for p in consumer.assignment():
                    low, high = consumer.get_watermark_offsets(p, timeout=10, cached=False)
                    metadata.observe(sink, topic, p.partition, low, high, counts)
                observed = time.monotonic()
    finally:
        # Unflushed records are intentionally replayed, including during rebalance/shutdown.
        consumer.close()
