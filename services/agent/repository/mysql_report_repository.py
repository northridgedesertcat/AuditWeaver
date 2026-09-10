# 分析报告 MySQL 写入仓库
# Agent 分析成功后直接 UPSERT 到 analysis_report 表（替代原 Kafka → Connect ES Sink 链路）。
# 表结构由 Django reports app 的 migration 创建，本模块不做任何 DDL。
#
# 设计要点：
# - PyMySQL 单连接 + ping(reconnect=True) 断线重连；
# - 写入语义与旧 ES Sink 一致：INSERT ... ON DUPLICATE KEY UPDATE（event_id 唯一键覆盖）；
# - 返回值约定与旧 AnalysisResultProducer.send 一致：成功 True / 失败 False，
#   由 main.py 的 send_retry 线性退避重试、失败进 DLQ。
import json
import logging
from typing import Any, Dict, Optional

import pymysql

from common.env import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
)
from common.time_utils import now_utc

logger = logging.getLogger('mysql_report_repository')

# 18 个业务列 + created_at/updated_at（Django auto_now 列无 DB 默认值，必须显式给值）：
# 列名、VALUES 占位符、参数 tuple 三处严格对齐。
_UPSERT_SQL = """
INSERT INTO analysis_report (
    event_id, ip, path, method, status, user_agent, detect_type,
    risk_level, risk_score, attack_type_ai, summary,
    reasoning, recommendations,
    log_timestamp, analysis_timestamp, ingestion_time,
    raw_response, original_log,
    created_at, updated_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s,
    %s, %s, %s,
    %s, %s,
    %s, %s
)
ON DUPLICATE KEY UPDATE
    ip = VALUES(ip),
    path = VALUES(path),
    method = VALUES(method),
    status = VALUES(status),
    user_agent = VALUES(user_agent),
    detect_type = VALUES(detect_type),
    risk_level = VALUES(risk_level),
    risk_score = VALUES(risk_score),
    attack_type_ai = VALUES(attack_type_ai),
    summary = VALUES(summary),
    reasoning = VALUES(reasoning),
    recommendations = VALUES(recommendations),
    log_timestamp = VALUES(log_timestamp),
    analysis_timestamp = VALUES(analysis_timestamp),
    ingestion_time = VALUES(ingestion_time),
    raw_response = VALUES(raw_response),
    original_log = VALUES(original_log),
    updated_at = VALUES(updated_at)
"""


class MySQLReportRepository:
    """analysis_report 表写入仓库（单连接，线程内使用）。"""

    def __init__(
        self,
        host: str = MYSQL_HOST,
        port: int = MYSQL_PORT,
        user: str = MYSQL_USER,
        password: str = MYSQL_PASSWORD,
        database: str = MYSQL_DATABASE,
    ):
        self._conn_params = {
            'host': host,
            'port': int(port),
            'user': user,
            'password': password,
            'database': database,
            'charset': 'utf8mb4',
            'autocommit': True,
            'connect_timeout': 10,
        }
        self._conn: Optional[pymysql.connections.Connection] = None

    def connect(self) -> bool:
        try:
            self._conn = pymysql.connect(**self._conn_params)
            logger.info(
                'MySQL connected: %s:%s/%s',
                self._conn_params['host'],
                self._conn_params['port'],
                self._conn_params['database'],
            )
            return True
        except Exception as e:
            logger.error('Failed to connect MySQL: %s', e)
            self._conn = None
            return False

    def _ensure_connection(self) -> bool:
        """连接不存在或断线时（重）连。"""
        if self._conn is not None:
            try:
                self._conn.ping(reconnect=True)
                return True
            except Exception:
                self._conn = None
        return self.connect()

    def upsert(self, record: Dict[str, Any]) -> bool:
        """按 event_id UPSERT 一行报告；失败返回 False（触发上层重试/DLQ）。"""
        if not self._ensure_connection():
            return False

        try:
            now_ts = now_utc()
            params = (
                record['event_id'],
                record.get('ip'),
                record.get('path', ''),
                record.get('method', ''),
                record.get('status'),
                record.get('user_agent', ''),
                record.get('detect_type', ''),
                record.get('risk_level', 'unknown'),
                record.get('risk_score', 0),
                record.get('attack_type_ai', ''),
                record.get('summary', ''),
                json.dumps(record.get('reasoning') or [], ensure_ascii=False),
                json.dumps(record.get('recommendations') or [], ensure_ascii=False),
                record.get('log_timestamp'),
                record.get('analysis_timestamp'),
                record.get('ingestion_time'),
                json.dumps(record['raw_response'], ensure_ascii=False)
                if record.get('raw_response') is not None else None,
                json.dumps(record['original_log'], ensure_ascii=False)
                if record.get('original_log') is not None else None,
                now_ts,
                now_ts,
            )
            with self._conn.cursor() as cur:
                cur.execute(_UPSERT_SQL, params)
            return True
        except Exception as e:
            logger.error(
                'MySQL upsert failed event_id=%s: %s',
                record.get('event_id'), e,
            )
            return False

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
            logger.info('MySQL connection closed')
