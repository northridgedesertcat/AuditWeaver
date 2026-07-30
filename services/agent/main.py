# Agent 模块主程序
import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import KAFKA_CONFIG, DIFY_CONFIG, LOG_CONFIG, PROCESS_CONFIG
from broker import LogAnalysisConsumer, AnalysisResultProducer
from dify import DifyClient
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
        self.dify_client = None
        self.running = False

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

        logger.info('Connecting to Dify API...')
        self.dify_client = DifyClient(
            base_url=DIFY_CONFIG['base_url'],
            api_key=DIFY_CONFIG['api_key'],
            timeout=DIFY_CONFIG['timeout'],
            endpoint=DIFY_CONFIG['endpoint']
        )
        logger.info('Dify client initialized')

        return True

    def process_log(self, raw_message: dict) -> bool:
        """管道: Dify 分析 → 构建文档 → 发送 Kafka"""
        event_id = raw_message.get('event_id', 'unknown')

        try:
            response = self.dify_client.analyze_log(raw_message)

            if response.get('status') == 'success':
                document = build_elastic_document(raw_message, response.get('response', {}))
                if self.kafka_producer.send(document, key=event_id):
                    logger.info(f'Processed: event_id={event_id}')
                    return True
                else:
                    logger.error(f'Kafka send failed: event_id={event_id}')
                    return False
            else:
                logger.error(f'Dify analysis failed: {response.get("error")}')
                return False

        except Exception as e:
            logger.error(f'Error processing {event_id}: {str(e)}')
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
        if self.dify_client:
            self.dify_client.close()
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
