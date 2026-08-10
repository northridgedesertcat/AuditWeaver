"""死信队列（DLQ）生产者。

自动将原始消息包装为标准 DLQ 格式，统一写入 ES logs_dead_letter 索引。
所有模块通过此类的 send_dlq() 发送失败消息，保证格式一致。
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .producer import KafkaBaseProducer

logger = logging.getLogger('dlq_producer')


class DlqProducer(KafkaBaseProducer):
    """死信队列生产者。

    在 send_dlq() 中自动包装标准 DLQ 格式：
        - @timestamp: ISO 格式 UTC 时间
        - event_id: 原始消息中的 event_id，无则生成 UUID
        - source_topic: 来源 topic
        - failed_stage: 失败阶段标识（如 rule_engine / agent / logstash_parser）
        - failure_reason: 失败原因简述
        - error_type / error_message / error_traceback: 异常详情
        - original_payload: 原始消息体（flattened 类型存储）
        - dlq_status: pending | replayed | resolved | ignored
        - retry_count: 重试次数
    """

    def __init__(
        self,
        bootstrap_servers: str | list[str],
        topic: str,
        failed_stage: str,
    ) -> None:
        super().__init__(bootstrap_servers, topic, acks='all', retries=3)
        self.failed_stage = failed_stage

    def send_dlq(
        self,
        original_payload: dict[str, Any],
        key: str | None = None,
        failure_reason: str = '',
        error: Exception | None = None,
        source_topic: str = '',
    ) -> None:
        """包装原始消息为标准 DLQ 格式并发送到死信队列。

        Args:
            original_payload: 处理失败的原始消息 dict
            key: Kafka 消息 key（默认使用 event_id）
            failure_reason: 失败原因简述（如 'grok_parse_failed'）
            error: 捕获的异常对象（可选，用于提取 error_type/error_message/traceback）
            source_topic: 原始消息来源 topic
        """
        event_id = str(original_payload.get('event_id', str(uuid4())))
        reason = failure_reason or (str(error) if error else 'unknown')

        dlq_message: dict[str, Any] = {
            '@timestamp': datetime.now(timezone.utc).isoformat(),
            'event_id': event_id,
            'source_topic': source_topic or self.topics[0],
            'failed_stage': self.failed_stage,
            'failure_reason': reason,
            'error_type': type(error).__name__ if error else '',
            'error_message': str(error) if error else '',
            'error_traceback': traceback.format_exc() if error else '',
            'original_payload': original_payload,
            'tags': ['dlq', self.failed_stage],
            'dlq_status': 'pending',
            'retry_count': 0,
            'log_source': original_payload.get('log_source', ''),
        }

        self.send(dlq_message, key=event_id)
        logger.info(
            'DLQ sent: stage=%s, event_id=%s, reason=%s',
            self.failed_stage, event_id, reason,
        )
