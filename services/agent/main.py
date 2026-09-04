# Agent 模块主程序
import sys
import os
import time
import logging

# 将 agent 目录加入 sys.path，以便导入 config/broker/dify 等模块
_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 将项目根目录加入 sys.path，以便导入 core 等公共模块
_PROJECT_ROOT = os.path.abspath(os.path.join(_AGENT_DIR, '..', '..'))
sys.path.insert(0, _AGENT_DIR)
sys.path.insert(0, _PROJECT_ROOT)

from tenacity import retry_if_result

from core.kafka.dlq import DlqProducer
from core.stable.circuit_breaker import CircuitBreaker
from core.stable.retry import Retry

from config import KAFKA_CONFIG, LOG_CONFIG, PROCESS_CONFIG, CIRCUIT_CONFIG
from broker import LogAnalysisConsumer, AnalysisResultProducer
from analysis import get_analysis_backend
from common.env import ANALYSIS_BACKEND
from preprocessor import build_elastic_document

logging.basicConfig(
    level=getattr(logging, LOG_CONFIG['level']),
    format=LOG_CONFIG['format']
)
logger = logging.getLogger('agent_main')


class AgentMain:
    def __init__(self):
        self.kafka_consumer = None
        self.kafka_producer = None
        self.dlq_producer = None
        self.analysis_backend = None
        self.running = False
        # 线性退避重试(配置见 agent.yaml process 段,等待序列 2s/4s/6s)
        # 分析后端:analyze 吞异常返回 AnalysisResult(status='failed'),按结果重试
        self.dify_retry = Retry(
            max_retries=PROCESS_CONFIG['retry_times'],
            base_delay=PROCESS_CONFIG['retry_delay'],
            max_delay=PROCESS_CONFIG['retry_max_delay'],
            retry=retry_if_result(lambda r: r.status == 'failed'),
            retry_error_callback=lambda rs: rs.outcome.result(),
        )
        # Kafka 发送:send() 失败返回 False,按返回值重试
        self.send_retry = Retry(
            max_retries=PROCESS_CONFIG['retry_times'],
            base_delay=PROCESS_CONFIG['retry_delay'],
            max_delay=PROCESS_CONFIG['retry_max_delay'],
            retry=retry_if_result(lambda sent: sent is False),
            retry_error_callback=lambda rs: rs.outcome.result(),
        )
        # 分析后端熔断:重试耗尽仍失败连续达到 fail_max 条后熔断,
        # 熔断期间不再调用后端,给其过载时喘息机会(配置见 agent.yaml circuit_breaker 段)
        self.dify_breaker = CircuitBreaker(
            fail_max=CIRCUIT_CONFIG['fail_max'],
            reset_timeout=CIRCUIT_CONFIG['reset_timeout'],
            success_threshold=CIRCUIT_CONFIG['success_threshold'],
            name='analysis',
            on_state_change=lambda old, new: logger.warning(
                f'分析后端熔断器状态变化: {old} -> {new}'
            ),
        )

    def initialize(self) -> bool:
        logger.info('Initializing Agent module...')

        logger.info('Connecting to Kafka consumer...')
        self.kafka_consumer = LogAnalysisConsumer(
            bootstrap_servers=KAFKA_CONFIG['brokers'],
            topic=KAFKA_CONFIG['input_topic'],
            group_id=KAFKA_CONFIG['group_id'],
            auto_offset_reset=KAFKA_CONFIG['auto_offset_reset'],
            consumer_timeout_ms=KAFKA_CONFIG['consumer_timeout_ms']
        )
        if not self.kafka_consumer.connect():
            logger.error('Failed to connect Kafka consumer')
            return False
        logger.info('Kafka consumer connected')

        logger.info('Connecting to Kafka producer...')
        self.kafka_producer = AnalysisResultProducer(
            bootstrap_servers=KAFKA_CONFIG['brokers'],
            topic=KAFKA_CONFIG['output_topic']
        )
        if not self.kafka_producer.connect():
            logger.error('Failed to connect Kafka producer')
            return False
        logger.info('Kafka producer connected')

        logger.info('Connecting to DLQ producer...')
        self.dlq_producer = DlqProducer(
            KAFKA_CONFIG['brokers'],
            KAFKA_CONFIG['dlq_topic'],
            failed_stage='agent',
        )
        self.dlq_producer.connect()
        logger.info('DLQ producer connected')

        logger.info('Initializing analysis backend...')
        self.analysis_backend = get_analysis_backend()
        logger.info(f'Analysis backend initialized: {ANALYSIS_BACKEND}')

        return True

    def process_log(self, raw_message: dict) -> bool:
        """管道: 分析后端 → 构建文档 → 发送 Kafka。失败时发送到 DLQ。"""
        event_id = raw_message.get('event_id', 'unknown')

        try:
            # 熔断包在重试外层:单条消息走完整线性退避重试,彻底失败计 1 次熔断失败;
            # 熔断打开时抛 CircuitOpenError(不再调用后端),消息快速失败进 DLQ
            response = self.dify_breaker.call(
                lambda msg: self.dify_retry.call(self.analysis_backend.analyze, msg),
                raw_message,
                result_is_failure=lambda r: r.status == 'failed',
            )

            if response.status == 'success':
                document = build_elastic_document(raw_message, response)
                if self.send_retry.call(self.kafka_producer.send, document, key=event_id):
                    logger.info(f'Processed: event_id={event_id}')
                    return True
                else:
                    logger.error(f'Kafka send failed: event_id={event_id}')
                    self.dlq_producer.send_dlq(
                        original_payload=raw_message,
                        key=event_id,
                        failure_reason='kafka_send_failed',
                        source_topic=KAFKA_CONFIG['input_topic'],
                    )
                    return False
            else:
                error = response.error or 'unknown'
                logger.error(f'Analysis failed: {error}')
                self.dlq_producer.send_dlq(
                    original_payload=raw_message,
                    key=event_id,
                    failure_reason=f'analysis_failed: {error}',
                    source_topic=KAFKA_CONFIG['input_topic'],
                )
                return False

        except Exception as e:
            logger.error(f'Error processing {event_id}: {str(e)}')
            self.dlq_producer.send_dlq(
                original_payload=raw_message,
                key=event_id,
                failure_reason='processing_exception',
                error=e,
                source_topic=KAFKA_CONFIG['input_topic'],
            )
            return False

    def run(self):
        logger.info('Agent module started')
        self.running = True

        batch_size = PROCESS_CONFIG['batch_size']
        poll_interval = PROCESS_CONFIG['poll_interval_ms'] / 1000.0

        while self.running:
            try:
                messages = self.kafka_consumer.consume(max_records=batch_size)

                if messages:
                    logger.info(f'Received {len(messages)} messages')

                    success_count = sum(1 for m in messages if self.process_log(m))
                    fail_count = len(messages) - success_count

                    logger.info(f'Batch complete: success={success_count}, failed={fail_count}')
                else:
                    logger.debug('No messages, waiting...')

                time.sleep(poll_interval)

            except KeyboardInterrupt:
                logger.info('Interrupt signal, stopping...')
                self.running = False
            except Exception as e:
                logger.error(f'Main loop error: {str(e)}')
                time.sleep(5)

        self.shutdown()

    def shutdown(self):
        logger.info('Shutting down Agent module...')
        if self.kafka_consumer:
            self.kafka_consumer.close()
        if self.kafka_producer:
            self.kafka_producer.close()
        if self.dlq_producer:
            self.dlq_producer.close()
        if self.analysis_backend:
            self.analysis_backend.close()
        logger.info('Agent module stopped')


def main():
    agent = AgentMain()
    if not agent.initialize():
        logger.error('Failed to initialize Agent module')
        sys.exit(1)
    try:
        agent.run()
    except Exception as e:
        logger.error(f'Fatal error: {str(e)}')
        sys.exit(1)


if __name__ == '__main__':
    main()
