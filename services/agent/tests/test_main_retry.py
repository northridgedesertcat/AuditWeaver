"""agent 模块线性退避重试集成测试(unittest)。

验证 process_log 接入 core.stable.retry 后的重试行为:
- 分析后端按返回值(status == 'failed')重试
- MySQL 写入(report_repo.upsert)按返回值(False)重试
- 重试耗尽后才进 DLQ,现有分支结构不变

运行方式(项目根目录,直接执行以先装载 kafka 桩模块):
    python services/agent/tests/test_main_retry.py

注:不要用 `python -m unittest services.agent.tests.test_main_retry` ——
unittest 加载测试模块前会先导入 services.agent 包(其 __init__ → broker → kafka),
此时桩模块尚未生效。
"""

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

# 预置 kafka 桩模块:规避 Python 3.13 下 kafka-python 2.0.2 无法导入
# (kafka.vendor.six.moves 兼容问题)的环境缺陷。本测试全程 mock broker/仓储
# 组件,真实 kafka 包不会被使用,故直接替换为桩即可保证跨环境可运行。
_kafka = types.ModuleType('kafka')
_kafka_errors = types.ModuleType('kafka.errors')
_kafka_errors.KafkaError = type('KafkaError', (Exception,), {})
_kafka.KafkaProducer = type('KafkaProducer', (), {})
_kafka.KafkaConsumer = type('KafkaConsumer', (), {})
_kafka.errors = _kafka_errors
sys.modules['kafka'] = _kafka
sys.modules['kafka.errors'] = _kafka_errors

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.agent.analysis.base import AnalysisResult
from services.agent.main import AgentMain


def _success_result() -> AnalysisResult:
    return AnalysisResult(
        status='success', log_id='e1',
        risk_level='High', risk_score=85,
        attack_type_ai='SQL注入', summary='发现注入行为',
        raw_response={'data': {'outputs': {}}},
    )


def _failed_result(error: str = 'boom') -> AnalysisResult:
    return AnalysisResult(status='failed', log_id='e1', error=error)


class AgentRetryIntegrationTests(unittest.TestCase):
    """验证 process_log 接入线性退避重试后的行为。"""

    def setUp(self) -> None:
        self.agent = AgentMain()
        self.agent.analysis_backend = mock.Mock()
        self.agent.report_repo = mock.Mock()
        self.agent.dlq_producer = mock.Mock()
        self.raw = {'event_id': 'e1', 'log_entry': {'event_id': 'e1'}}

    def test_first_call_success_no_retry(self) -> None:
        self.agent.analysis_backend.analyze.return_value = _success_result()
        self.agent.report_repo.upsert.return_value = True

        with mock.patch('time.sleep'):
            result = self.agent.process_log(self.raw)

        self.assertTrue(result)
        self.agent.analysis_backend.analyze.assert_called_once()
        self.agent.report_repo.upsert.assert_called_once()
        self.agent.dlq_producer.send_dlq.assert_not_called()

    def test_analysis_retries_then_succeeds(self) -> None:
        self.agent.analysis_backend.analyze.side_effect = [
            _failed_result('t1'),
            _failed_result('t2'),
            _success_result(),
        ]
        self.agent.report_repo.upsert.return_value = True

        with mock.patch('time.sleep'):
            result = self.agent.process_log(self.raw)

        self.assertTrue(result)
        self.assertEqual(self.agent.analysis_backend.analyze.call_count, 3)
        self.agent.dlq_producer.send_dlq.assert_not_called()

    def test_analysis_exhausted_goes_to_dlq(self) -> None:
        self.agent.analysis_backend.analyze.return_value = _failed_result()

        with mock.patch('time.sleep'):
            result = self.agent.process_log(self.raw)

        self.assertFalse(result)
        # 首次 + 3 次重试
        self.assertEqual(self.agent.analysis_backend.analyze.call_count, 4)
        self.agent.dlq_producer.send_dlq.assert_called_once()
        reason = self.agent.dlq_producer.send_dlq.call_args.kwargs['failure_reason']
        self.assertTrue(reason.startswith('analysis_failed'))
        self.agent.report_repo.upsert.assert_not_called()

    def test_analysis_wait_sequence_is_linear(self) -> None:
        self.agent.analysis_backend.analyze.return_value = _failed_result()

        with mock.patch('time.sleep') as sleep_mock:
            self.agent.process_log(self.raw)

        # 线性退避:2s -> 4s -> 6s(config: retry_delay=2, retry_max_delay=10)
        self.assertEqual([c.args[0] for c in sleep_mock.call_args_list], [2.0, 4.0, 6.0])

    def test_upsert_retries_then_succeeds(self) -> None:
        self.agent.analysis_backend.analyze.return_value = _success_result()
        self.agent.report_repo.upsert.side_effect = [False, True]

        with mock.patch('time.sleep'):
            result = self.agent.process_log(self.raw)

        self.assertTrue(result)
        self.assertEqual(self.agent.report_repo.upsert.call_count, 2)
        self.agent.dlq_producer.send_dlq.assert_not_called()

    def test_upsert_exhausted_goes_to_dlq(self) -> None:
        self.agent.analysis_backend.analyze.return_value = _success_result()
        self.agent.report_repo.upsert.return_value = False

        with mock.patch('time.sleep'):
            result = self.agent.process_log(self.raw)

        self.assertFalse(result)
        # 首次 + 3 次重试
        self.assertEqual(self.agent.report_repo.upsert.call_count, 4)
        self.agent.dlq_producer.send_dlq.assert_called_once()
        reason = self.agent.dlq_producer.send_dlq.call_args.kwargs['failure_reason']
        self.assertEqual(reason, 'db_write_failed')


if __name__ == '__main__':
    unittest.main()
