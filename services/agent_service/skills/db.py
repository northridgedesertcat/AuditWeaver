"""Skills 共用的 MySQL 只读客户端（AI 分析报告查询）。

- 直接从 ``common.env`` 读取连接参数,不依赖 Django(本进程是 MCP Server 子进程)。
- 目标表 ``analysis_report`` 由 Django reports app 的 migration 创建,
  本模块只读,不提供任何写操作、不做任何 DDL。
- 连接风格与 ``skills/es.py`` 一致:单例 + 断线重连,异常返回 None 不抛栈。
"""
import pymysql
import pymysql.cursors

from common.env import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
)

_conn = None
_conn_ok: bool | None = None


def get_connection():
    """返回单例 MySQL 连接(DictCursor);连接失败返回 None,断线自动重连。"""
    global _conn
    if _conn is not None:
        try:
            _conn.ping(reconnect=True)
            return _conn
        except Exception:
            _conn = None
    try:
        _conn = pymysql.connect(
            host=MYSQL_HOST,
            port=int(MYSQL_PORT),
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=10,
        )
        return _conn
    except Exception:
        _conn = None
        return None


def is_db_available() -> bool:
    global _conn_ok
    if _conn_ok is not None:
        return _conn_ok
    _conn_ok = get_connection() is not None
    return _conn_ok


def query(sql: str, params: tuple | None = None) -> list[dict] | None:
    """安全查询包装:MySQL 不可用或异常时返回 None,不抛栈。"""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    except Exception:
        return None
