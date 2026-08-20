"""Skills 共用的 Elasticsearch 客户端。

- 直接从 ``common.env`` 读取连接参数,不依赖 Django(本进程是 MCP Server 子进程)。
- 与 ``services/website/backend/v1/api/es_client.py`` 使用同一套 ES 配置,保证两侧一致。
- 所有 Skill 只读,本模块不提供任何写操作。
"""
from elasticsearch import Elasticsearch

from common.env import (
    ES_HOST,
    ES_PORT,
    ES_USER,
    ES_PASSWORD,
    ES_SCHEME,
    ES_USE_SSL,
    ES_VERIFY_CERTS,
)

_client: Elasticsearch | None = None
_client_ok: bool | None = None


def get_es_client() -> Elasticsearch | None:
    """返回单例 ES 客户端;连接失败返回 None。"""
    global _client
    if _client is not None:
        return _client
    try:
        scheme = "https" if ES_USE_SSL else (ES_SCHEME or "http")
        _client = Elasticsearch(
            hosts=[f"{scheme}://{ES_HOST}:{ES_PORT}"],
            basic_auth=(ES_USER, ES_PASSWORD),
            verify_certs=ES_VERIFY_CERTS,
            ssl_show_warn=False,
            request_timeout=30,
            max_retries=3,
            retry_on_timeout=True,
        )
        return _client
    except Exception:
        _client = None
        return None


def is_es_available() -> bool:
    global _client_ok
    if _client_ok is not None:
        return _client_ok
    es = get_es_client()
    if es is None:
        _client_ok = False
        return False
    try:
        _client_ok = bool(es.ping())
        return _client_ok
    except Exception:
        _client_ok = False
        return False


def search(index: str, body: dict) -> dict | None:
    """安全查询包装:ES 不可用或异常时返回 None,不抛栈。"""
    es = get_es_client()
    if es is None:
        return None
    try:
        return es.search(index=index, body=body)
    except Exception:
        return None
