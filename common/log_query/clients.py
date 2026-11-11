from __future__ import annotations

import re
from datetime import timezone
from common import env


def es_client():
    from elasticsearch import Elasticsearch
    scheme = "https" if env.ES_USE_SSL else env.ES_SCHEME
    return Elasticsearch(
        f"{scheme}://{env.ES_HOST}:{env.ES_PORT}", basic_auth=(env.ES_USER, env.ES_PASSWORD),
        verify_certs=env.ES_VERIFY_CERTS, request_timeout=30, max_retries=2,
    )


def ck_client(*, writer=False, admin=False):
    import clickhouse_connect
    role = "ADMIN" if admin else "WRITER" if writer else "READER"
    username = env.get_env(f"CK_{role}_USER", f"auditweaver_{role.lower()}")
    password = env.get_env(f"CK_{role}_PASSWORD")
    if not password:
        raise ValueError(f"CK_{role}_PASSWORD is required")
    return clickhouse_connect.get_client(
        host=env.get_env("CK_HOST", "localhost"), port=env.get_env_int("CK_HTTP_PORT", 18123),
        username=username, password=password, secure=env.get_env_bool("CK_SECURE"),
        database="default" if admin else database(), connect_timeout=5, send_receive_timeout=30,
        settings={"max_memory_usage": 536870912, "max_threads": 2, "max_execution_time": 30},
    )


def database():
    name = env.get_env("CK_DATABASE", "auditweaver_logs")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
        raise ValueError("Invalid CK_DATABASE identifier")
    return name


def decode_ck_time(value):
    # clickhouse-connect returns naive datetimes for a UTC DateTime64 column.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
