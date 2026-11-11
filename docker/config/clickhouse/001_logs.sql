CREATE DATABASE IF NOT EXISTS {database};

CREATE TABLE IF NOT EXISTS {database}.raw_logs
(
    record_id String,
    event_id String,
    event_time DateTime64(3, 'UTC'),
    ingested_at Nullable(DateTime64(3, 'UTC')),
    archived_at DateTime64(3, 'UTC'),
    ip String,
    method LowCardinality(String),
    path String,
    normalized_path String,
    status Nullable(UInt16),
    bytes Nullable(UInt64),
    http_version LowCardinality(String),
    referrer String,
    user_agent String,
    log_source LowCardinality(String),
    attack_types Array(String),
    rule_ids Array(String),
    raw_payload String CODEC(ZSTD(3)),
    payload_hash FixedString(64),
    schema_version UInt16,
    source_kind LowCardinality(String),
    source_topic String,
    source_partition Int32,
    source_offset Int64,
    version UInt64
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, record_id);

CREATE TABLE IF NOT EXISTS {database}.security_events AS {database}.raw_logs
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, record_id);
