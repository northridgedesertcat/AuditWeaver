#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AuditWeaver - Kafka Topic Initializer

Reads topics.yaml and creates missing Kafka topics via confluent-kafka AdminClient.
Existing topics are left untouched (no partition/config changes applied).

底层使用 confluent-kafka（librdkafka），规避 Windows 上 kafka-python 的
SelectSelector 兼容问题。原 kafka-python 的 create_topics 抛 TopicAlreadyExistsError，
confluent 改为返回 {topic: Future}，逐个 f.result() 取结果，已存在用字符串匹配识别。

Usage:
    python create-init-topics.py
    python create-init-topics.py --brokers localhost:29092
    python create-init-topics.py --config /path/to/topics.yaml
    python create-init-topics.py --dry-run
    python create-init-topics.py --list-only
"""

import argparse
import sys
import os
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('init-topics')

try:
    import yaml
except ImportError:
    log.error("PyYAML is required. Install it via: pip install pyyaml")
    sys.exit(1)

try:
    from confluent_kafka.admin import AdminClient, NewTopic
    from confluent_kafka.error import KafkaException
except ImportError:
    log.error("confluent-kafka is required. Install it via: pip install confluent-kafka")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_default_brokers():
    """Try to resolve default bootstrap servers from the project .env file."""
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent.parent
    env_file = project_root / '.env'

    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, _, val = line.partition('=')
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key == 'KAFKA_BROKERS' and val:
                        return val
                    if key == 'KAFKA_PORT' and val:
                        return f'localhost:{val}'
        except Exception:
            pass

    return 'localhost:29092'


def load_topics_config(yaml_path: str) -> list:
    """Load topic definitions from the YAML file."""
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {yaml_path}")

    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if not data or 'topics' not in data:
        raise ValueError(f"Invalid config: 'topics' key missing in {yaml_path}")

    topics = []
    for entry in data['topics']:
        name = entry.get('name')
        if not name:
            raise ValueError(f"Invalid entry (missing 'name'): {entry}")
        partitions = int(entry.get('partitions', 1))
        replication_factor = int(entry.get('replication_factor', 1))
        configs = entry.get('configs', {}) or {}

        topics.append({
            'name': name,
            'partitions': partitions,
            'replication_factor': replication_factor,
            'configs': configs,
        })

    return topics


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def list_existing_topics(admin_client: AdminClient) -> set:
    """Return the set of topic names that already exist on the cluster."""
    try:
        # confluent-kafka 的 list_topics 参数为 timeout(秒),非 timeout_ms
        cluster_meta = admin_client.list_topics(timeout=15)
        return set(cluster_meta.topics.keys())
    except KafkaException as e:
        raise RuntimeError(f"Failed to list topics: {e}") from e


def create_topics(admin_client: AdminClient, topics: list, dry_run: bool = False):
    """Create topics that do not already exist. Existing topics are skipped.
    Returns (created_count, failed_count).
    """
    existing = list_existing_topics(admin_client)

    to_create = []
    for t in topics:
        if t['name'] in existing:
            log.info(f"[SKIP] Topic already exists: {t['name']}")
            continue
        to_create.append(
            NewTopic(
                topic=t['name'],
                num_partitions=t['partitions'],
                replication_factor=t['replication_factor'],
                # confluent-kafka 要求 config 为 dict of strings，不接受 None；
                # load_topics_config 已保证 configs 为 dict（无配置时为空 dict）
                config=t['configs'],
            )
        )
        log.info(
            f"[PLAN] Create topic '{t['name']}' "
            f"(partitions={t['partitions']}, "
            f"replication={t['replication_factor']})"
        )

    if not to_create:
        log.info("All topics are already up to date. Nothing to create.")
        return 0, 0

    if dry_run:
        log.info(f"[DRY-RUN] {len(to_create)} topic(s) would be created. "
                 "No changes applied.")
        return len(to_create), 0

    log.info(f"Creating {len(to_create)} topic(s) ...")
    # confluent 的 create_topics 返回 {topic_name: Future}，需逐个取 result
    future_map = admin_client.create_topics(to_create, validate_only=False)
    created_count = 0
    failed_count = 0
    for topic_name, future in future_map.items():
        try:
            future.result()  # 阻塞等待，失败抛 KafkaException
            created_count += 1
            log.info(f"[OK] Created topic '{topic_name}'")
        except KafkaException as e:
            msg_str = str(e).lower()
            if 'already exists' in msg_str or 'topicalreadyexists' in msg_str:
                log.info(f"[SKIP] Topic already exists: {topic_name}")
            else:
                log.error(f"[FAIL] Failed to create topic '{topic_name}': {e}")
                failed_count += 1
        except Exception as e:
            log.error(f"[FAIL] Failed to create topic '{topic_name}': {e}")
            failed_count += 1

    log.info(f"Topic creation completed. created={created_count}, failed={failed_count}")
    return created_count, failed_count


def show_status(admin_client: AdminClient, topics: list):
    """Print status of each configured topic against the cluster."""
    existing = list_existing_topics(admin_client)
    log.info("=" * 60)
    log.info("Topic status on cluster:")
    log.info("=" * 60)
    for t in topics:
        state = "EXISTS" if t['name'] in existing else "MISSING"
        log.info(
            f"  [{state:7s}] {t['name']} "
            f"(partitions={t['partitions']}, "
            f"replication={t['replication_factor']})"
        )
    log.info("=" * 60)


def connect_brokers(brokers: str) -> AdminClient:
    """Establish an admin client connection to the Kafka cluster."""
    log.info(f"Connecting to Kafka brokers: {brokers}")
    try:
        admin = AdminClient({
            'bootstrap.servers': brokers,
            'request.timeout.ms': 15000,
        })
        # AdminClient 构造不立即连接，用 list_topics 探测（模拟原 NoBrokersAvailable 语义）
        admin.list_topics(timeout=15)
        log.info("Connected successfully.")
        return admin
    except KafkaException as e:
        raise RuntimeError(
            f"No brokers available at '{brokers}' or failed to connect: {e}. "
            "Make sure Kafka is running and the address is correct."
        ) from e
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Kafka: {e}") from e


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    default_yaml = Path(__file__).resolve().parent / 'topics.yaml'

    parser = argparse.ArgumentParser(
        description='Initialize AuditWeaver Kafka topics from topics.yaml',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--brokers',
        default=None,
        help='Kafka bootstrap servers (default: auto-detect from .env or localhost:29092)',
    )
    parser.add_argument(
        '--config',
        default=str(default_yaml),
        help='Path to topics.yaml (default: %(default)s)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be created without actually creating anything',
    )
    parser.add_argument(
        '--list-only',
        action='store_true',
        help='Only show current topic status, do not create anything',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable debug-level logging',
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    brokers = args.brokers or resolve_default_brokers()
    yaml_path = args.config

    log.info(f"Config file: {yaml_path}")
    log.info(f"Brokers:     {brokers}")

    try:
        topics = load_topics_config(yaml_path)
    except (FileNotFoundError, ValueError) as e:
        log.error(str(e))
        sys.exit(1)

    log.info(f"Loaded {len(topics)} topic definition(s) from config.")

    try:
        admin = connect_brokers(brokers)
    except RuntimeError as e:
        log.error(str(e))
        sys.exit(1)

    # confluent-kafka 的 AdminClient 没有 close()，无需显式关闭
    try:
        if args.list_only:
            show_status(admin, topics)
        else:
            show_status(admin, topics)
            created, failed = create_topics(admin, topics, dry_run=args.dry_run)
            show_status(admin, topics)
            if failed > 0:
                log.error(f"{failed} topic(s) failed to be created.")
                sys.exit(1)
    finally:
        log.info("Admin client done.")


if __name__ == '__main__':
    main()
