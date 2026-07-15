# Agent 模块主程序
import sys
import os
import time
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import KAFKA_CONFIG, DIFY_CONFIG, ELASTICSEARCH_CONFIG, LOG_CONFIG, PROCESS_CONFIG
from kafka_consumer import LogAnalysisConsumer
from dify import DifyClient
from es_client import DataSaver

logging.basicConfig(
    level=getattr(logging, LOG_CONFIG['level']),
    format=LOG_CONFIG['format']
)
logger = logging.getLogger('agent_main')

class AgentMain:
    def __init__(self):
        self.kafka_consumer = None
        self.dify_client = None
        self.data_saver = None
        self.running = False

    def initialize(self) -> bool:
        logger.info('Initializing Agent module...')

        logger.info('Connecting to Kafka...')
        self.kafka_consumer = LogAnalysisConsumer(
            bootstrap_servers=KAFKA_CONFIG['brokers'],
            topic=KAFKA_CONFIG['input_topic'],
            group_id=KAFKA_CONFIG['group_id'],
            auto_offset_reset=KAFKA_CONFIG['auto_offset_reset'],
            consumer_timeout_ms=KAFKA_CONFIG['consumer_timeout_ms']
        )
        if not self.kafka_consumer.connect():
            logger.error('Failed to connect to Kafka')
            return False
        logger.info('Kafka connected successfully')

        logger.info('Connecting to Dify API...')
        self.dify_client = DifyClient(
            base_url=DIFY_CONFIG['base_url'],
            api_key=DIFY_CONFIG['api_key'],
            timeout=DIFY_CONFIG['timeout'],
            endpoint=DIFY_CONFIG['endpoint']
        )
        logger.info('Dify client initialized')

        logger.info('Connecting to Elasticsearch...')
        self.data_saver = DataSaver(
            es_host=ELASTICSEARCH_CONFIG['host'],
            es_port=ELASTICSEARCH_CONFIG['port'],
            es_index=ELASTICSEARCH_CONFIG['index']
        )
        if not self.data_saver.connect():
            logger.error('Failed to connect to Elasticsearch')
            return False
        logger.info('Elasticsearch connected successfully')

        return True

    def process_log(self, log_entry: dict) -> bool:
        if 'log_entry' in log_entry:
            actual_log = log_entry.get('log_entry', {})
        else:
            actual_log = log_entry

        event_id = actual_log.get('event_id', 'unknown')
        ip = actual_log.get('ip', 'unknown')
        detection_result = actual_log.get('detection_result', actual_log.get('rule_match', {}))
        attack_type = detection_result.get('attack_type', detection_result.get('matched_type', 'unknown'))

        logger.info(f'Processing log: event_id={event_id}, ip={ip}, attack_type={attack_type}')

        try:
            dify_response = self.dify_client.analyze_log(actual_log)

            if dify_response.get('status') == 'success':
                doc_id = self.data_saver.save_analysis_report(actual_log, dify_response.get('response', {}))
                if doc_id:
                    logger.info(f'Analysis report saved: {doc_id}')
                    return True
                else:
                    logger.error('Failed to save analysis report')
                    return False
            else:
                logger.error(f'Dify analysis failed: {dify_response.get("error")}')
                return False

        except Exception as e:
            logger.error(f'Error processing log {event_id}: {str(e)}')
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
                    logger.info(f'Received {len(messages)} messages from Kafka')

                    success_count = 0
                    fail_count = 0

                    for log_entry in messages:
                        if self.process_log(log_entry):
                            success_count += 1
                        else:
                            fail_count += 1

                    logger.info(f'Processing complete: success={success_count}, failed={fail_count}')
                else:
                    logger.debug('No messages received, waiting...')

                time.sleep(poll_interval)

            except KeyboardInterrupt:
                logger.info('Received interrupt signal, stopping...')
                self.running = False
            except Exception as e:
                logger.error(f'Error in main loop: {str(e)}')
                time.sleep(5)

        self.shutdown()

    def shutdown(self):
        logger.info('Shutting down Agent module...')
        if self.kafka_consumer:
            self.kafka_consumer.close()
        if self.dify_client:
            self.dify_client.close()
        if self.data_saver:
            self.data_saver.close()
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
