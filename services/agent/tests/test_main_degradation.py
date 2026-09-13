"""agent 模块降级集成测试(unittest)。

验证 process_log 接入 CircuitBreaker fallback 后的降级行为:
- 熔断打开期走 fallback 产出降级报告(仅规则匹配),不进 DLQ,落库后 offset 正常提交
- 熔断器按"完整 analyze 调用最终结果"计数,Retry 内部尝试不计(2.3.1)
- Half-Open 探测走真实 analyze(含重试),不走 fallback;Retry 后成功视为探测成功(7.2)
- risk_score=0 是 NOT NULL 占位,降级唯一标识是 raw_response.degraded(2.5 消费者契约)

运行方式(项目根目录,直接执行以先装载 kafka 桩模块):
    python services/agent/tests/test_main_degradation.py

注:不要用 `python -m unittest services.agent.tests.test_main_degradation` ——
unittest 加载测试模块前会先导入 services.agent 包(其 __init__ → broker → kafka),
此时桩模块尚未生效。
"""

import sys
import time
import types
import unittest
from pathlib import Path
from unittest import mock

# 预置 kafka 桩模块:规避 Python 3.13 下 kafka-python 2.0.2 无法导入
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
from services.agent.config.settings import CIRCUIT_CONFIG, PROCESS_CONFIG
from core.stable.circuit_breaker import CircuitBreaker

# 真实 time.sleep 引用:Half-Open 转换需真实等待 reset_timeout,
# mock.patch('time.sleep') 期间用此引用绕过 mock 做真实等待
_REAL_SLEEP = time.sleep


def _success_result(event_id='e1') -> AnalysisResult:
    return AnalysisResult(
        status='success', log_id=event_id,
        risk_level='High', risk_score=85,
        attack_type_ai='SQL注入', summary='发现注入行为',
        raw_response={'data': {'outputs': {}}},
    )


def _failed_result(error='boom', event_id='e1') -> AnalysisResult:
    return AnalysisResult(status='failed', log_id=event_id, error=error)


def _degraded_result(event_id='e1') -> AnalysisResult:
    return AnalysisResult(
        status='degraded', log_id=event_id,
        risk_level='unknown', risk_score=0,
        attack_type_ai='', summary='',
        raw_response={'degraded': True, 'reason': 'circuit_open'},
    )


def _raw_message(event_id='e1', attack_type='SQL注入'):
    """规则引擎 v2 输出格式:含 attack_type 与 log_context 的规则字段。"""
    return {
        'event_id': event_id,
        'attack_type': attack_type,
        'log_context': {
            'ip': '1.2.3.4', 'path': '/login', 'method': 'POST',
            'status': 200, 'user_agent': 'Mozilla',
            'timestamp': 1700000000000,
        },
    }


class DegradationIntegrationTests(unittest.TestCase):
    """验证熔断打开期 fallback 降级行为(方案主表 8 用例)。"""

    def setUp(self) -> None:
        self.agent = AgentMain()
        self.agent.analysis_backend = mock.Mock()
        self.agent.report_repo = mock.Mock()
        self.agent.dlq_producer = mock.Mock()
        self.agent.report_repo.upsert.return_value = True

    def _make_fast_breaker(self) -> CircuitBreaker:
        """构造小 reset_timeout 熔断器,便于测试 OPEN→HALF_OPEN 转换。"""
        return CircuitBreaker(
            fail_max=3, reset_timeout=0.05, success_threshold=2, name='analysis',
        )

    # --- 主表 8 用例 ---

    def test_circuit_open_triggers_degradation(self) -> None:
        # 连续 3 条 analyze 全失败(每条 4 次调用)→ 熔断 OPEN → 第 4 条走 fallback 降级
        self.agent.analysis_backend.analyze.return_value = _failed_result()
        with mock.patch('time.sleep'):
            for i in range(3):
                self.agent.process_log(_raw_message(f'e{i+1}'))
            self.assertEqual(self.agent.dify_breaker.state, 'open')
            # 第 4 条:熔断打开 → fallback 降级报告
            result = self.agent.process_log(_raw_message('e4'))
        # 降级走成功落库路径,返回 True
        self.assertTrue(result)
        # 前 3 条进 DLQ(分析失败),第 4 条降级不进 DLQ
        self.assertEqual(self.agent.dlq_producer.send_dlq.call_count, 3)
        # 第 4 条调用了 upsert(降级落库)
        self.assertEqual(self.agent.report_repo.upsert.call_count, 1)
        # analyze 共 3×4=12 次(第 4 条走 fallback 不调 analyze)
        self.assertEqual(self.agent.analysis_backend.analyze.call_count, 12)

    def test_degraded_report_no_ai_fields(self) -> None:
        from services.agent.preprocessor import build_degraded_result
        result = build_degraded_result(_raw_message())
        self.assertEqual(result.status, 'degraded')
        self.assertEqual(result.risk_level, 'unknown')
        self.assertEqual(result.risk_score, 0)
        self.assertEqual(result.attack_type_ai, '')
        self.assertEqual(result.summary, '')
        self.assertEqual(result.reasoning, [])
        self.assertEqual(result.recommendations, [])
        self.assertTrue(result.raw_response.get('degraded'))

    def test_degraded_report_keeps_rule_fields(self) -> None:
        from services.agent.preprocessor import build_report_record, build_degraded_result
        raw = _raw_message(attack_type='SQL注入')
        record = build_report_record(raw, build_degraded_result(raw))
        # 规则字段来自 raw_message,降级不影响
        self.assertEqual(record['event_id'], 'e1')
        self.assertEqual(record['detect_type'], 'SQL注入')
        self.assertEqual(record['ip'], '1.2.3.4')
        self.assertEqual(record['path'], '/login')
        self.assertEqual(record['method'], 'POST')

    def test_degraded_not_go_dlq(self) -> None:
        self.agent.analysis_backend.analyze.return_value = _failed_result()
        with mock.patch('time.sleep'):
            for i in range(3):
                self.agent.process_log(_raw_message(f'e{i+1}'))
            # 第 4 条降级
            result = self.agent.process_log(_raw_message('e4'))
        self.assertTrue(result)
        # 仅前 3 条进 DLQ,降级那条不进
        self.assertEqual(self.agent.dlq_producer.send_dlq.call_count, 3)

    def test_half_open_probe_skips_fallback(self) -> None:
        self.agent.dify_breaker = self._make_fast_breaker()
        self.agent.analysis_backend.analyze.return_value = _failed_result()
        with mock.patch('time.sleep'):
            for i in range(3):
                self.agent.process_log(_raw_message(f'e{i+1}'))
            self.assertEqual(self.agent.dify_breaker.state, 'open')
        # 真实等待 reset_timeout → 下次调用转 HALF_OPEN
        _REAL_SLEEP(0.07)
        # 探测:analyze 成功(连续 2 条 → CLOSED 恢复全量 AI)
        self.agent.analysis_backend.analyze.return_value = _success_result()
        with mock.patch('time.sleep'):
            self.agent.process_log(_raw_message('e4'))  # 第 1 次探测成功
            self.assertEqual(self.agent.dify_breaker.state, 'half-open')
            self.agent.process_log(_raw_message('e5'))  # 第 2 次成功 → CLOSED
            self.assertEqual(self.agent.dify_breaker.state, 'closed')
        # 探测期调用了真实 analyze(12 失败 + 2 探测),未走 fallback
        self.assertEqual(self.agent.analysis_backend.analyze.call_count, 14)

    def test_half_open_probe_fail_reopens(self) -> None:
        self.agent.dify_breaker = self._make_fast_breaker()
        self.agent.analysis_backend.analyze.return_value = _failed_result()
        with mock.patch('time.sleep'):
            for i in range(3):
                self.agent.process_log(_raw_message(f'e{i+1}'))
            self.assertEqual(self.agent.dify_breaker.state, 'open')
        _REAL_SLEEP(0.07)  # → HALF_OPEN
        with mock.patch('time.sleep'):
            # 半开探测失败 → 重新 OPEN
            self.agent.process_log(_raw_message('e4'))
            self.assertEqual(self.agent.dify_breaker.state, 'open')
            # 紧接着下一条仍 OPEN(reset_timeout 未到)→ fallback 降级
            result = self.agent.process_log(_raw_message('e5'))
            self.assertTrue(result)  # 降级落库

    def test_jitter_configured(self) -> None:
        self.assertEqual(self.agent.dify_retry.config.jitter, PROCESS_CONFIG['retry_jitter'])
        self.assertEqual(self.agent.send_retry.config.jitter, PROCESS_CONFIG['retry_jitter'])
        self.assertGreater(PROCESS_CONFIG['retry_jitter'], 0)

    def test_fail_max_is_three(self) -> None:
        self.assertEqual(CIRCUIT_CONFIG['fail_max'], 3)
        self.assertEqual(self.agent.dify_breaker.config.fail_max, 3)


class CircuitCounterSemanticsTests(unittest.TestCase):
    """验证熔断器按完整 analyze 调用最终结果计数,Retry 内部尝试不计(7.1,5 用例)。"""

    def setUp(self) -> None:
        self.agent = AgentMain()
        self.agent.analysis_backend = mock.Mock()
        self.agent.report_repo = mock.Mock()
        self.agent.dlq_producer = mock.Mock()
        self.agent.report_repo.upsert.return_value = True

    def test_retry_attempts_not_counted_as_circuit_failures(self) -> None:
        self.agent.analysis_backend.analyze.return_value = _failed_result()
        with mock.patch('time.sleep'):
            self.agent.process_log(_raw_message('e1'))
        # 4 次真实 analyze 调用(1 首次 + 3 重试)
        self.assertEqual(self.agent.analysis_backend.analyze.call_count, 4)
        # 熔断器只计 1 次失败(完整调用最终结果),不是 3/4 次
        self.assertEqual(self.agent.dify_breaker.fail_counter, 1)
        self.assertEqual(self.agent.dify_breaker.state, 'closed')

    def test_single_message_retry_exhaust_not_open_circuit(self) -> None:
        self.agent.analysis_backend.analyze.return_value = _failed_result()
        with mock.patch('time.sleep'):
            result = self.agent.process_log(_raw_message('e1'))
        self.assertFalse(result)
        self.assertEqual(self.agent.dify_breaker.fail_counter, 1)
        self.assertEqual(self.agent.dify_breaker.state, 'closed')  # 1 < 3,未熔断
        self.agent.dlq_producer.send_dlq.assert_called_once()
        reason = self.agent.dlq_producer.send_dlq.call_args.kwargs['failure_reason']
        self.assertTrue(reason.startswith('analysis_failed'))

    def test_two_messages_retry_exhaust_not_open(self) -> None:
        self.agent.analysis_backend.analyze.return_value = _failed_result()
        with mock.patch('time.sleep'):
            self.agent.process_log(_raw_message('e1'))
            self.agent.process_log(_raw_message('e2'))
        self.assertEqual(self.agent.dify_breaker.fail_counter, 2)
        self.assertEqual(self.agent.dify_breaker.state, 'closed')  # 2 < 3
        self.assertEqual(self.agent.dlq_producer.send_dlq.call_count, 2)

    def test_three_messages_retry_exhaust_opens(self) -> None:
        self.agent.analysis_backend.analyze.return_value = _failed_result()
        with mock.patch('time.sleep'):
            for i in range(3):
                self.agent.process_log(_raw_message(f'e{i+1}'))
            self.assertEqual(self.agent.dify_breaker.state, 'open')
            # 前 3 条进 DLQ(分析失败,非降级)
            self.assertEqual(self.agent.dlq_producer.send_dlq.call_count, 3)
            # 第 4 条走 fallback 降级,不进 DLQ,落库
            result = self.agent.process_log(_raw_message('e4'))
            self.assertTrue(result)
        self.assertEqual(self.agent.dlq_producer.send_dlq.call_count, 3)  # 降级不进 DLQ
        self.assertEqual(self.agent.report_repo.upsert.call_count, 1)

    def test_retry_success_resets_fail_counter(self) -> None:
        self.agent.analysis_backend.analyze.return_value = _failed_result()
        with mock.patch('time.sleep'):
            # 先 2 条失败 → fail_counter=2
            self.agent.process_log(_raw_message('e1'))
            self.agent.process_log(_raw_message('e2'))
            self.assertEqual(self.agent.dify_breaker.fail_counter, 2)
            # 第 3 条:首次 failed,重试第 2 次成功 → 熔断计 1 次成功 → 清零
            self.agent.analysis_backend.analyze.side_effect = [
                _failed_result(), _success_result()
            ]
            self.agent.process_log(_raw_message('e3'))
        # 成功 → fail_counter 清零,状态 CLOSED
        self.assertEqual(self.agent.dify_breaker.fail_counter, 0)
        self.assertEqual(self.agent.dify_breaker.state, 'closed')


class HalfOpenRetryTests(unittest.TestCase):
    """验证 Half-Open + Retry 行为:探测走真实 analyze(含重试),不走 fallback(7.2,4 用例)。"""

    def setUp(self) -> None:
        self.agent = AgentMain()
        self.agent.analysis_backend = mock.Mock()
        self.agent.report_repo = mock.Mock()
        self.agent.dlq_producer = mock.Mock()
        self.agent.report_repo.upsert.return_value = True
        self.agent.dify_breaker = CircuitBreaker(
            fail_max=3, reset_timeout=0.05, success_threshold=2, name='analysis',
        )

    def _trip_to_open(self) -> None:
        """在 mock sleep 下连续 3 条失败 → 熔断 OPEN。"""
        self.agent.analysis_backend.analyze.return_value = _failed_result()
        with mock.patch('time.sleep'):
            for i in range(3):
                self.agent.process_log(_raw_message(f'e{i+1}'))
            self.assertEqual(self.agent.dify_breaker.state, 'open')

    def test_half_open_probe_retry_then_success_counts_as_success(self) -> None:
        self._trip_to_open()
        _REAL_SLEEP(0.07)  # → HALF_OPEN
        # 探测:首次 failed,Retry 第 2 次成功 → 视为本次探测成功(不重开)
        self.agent.analysis_backend.analyze.side_effect = [
            _failed_result(), _success_result()
        ]
        with mock.patch('time.sleep'):
            self.agent.process_log(_raw_message('e4'))
            self.assertEqual(self.agent.dify_breaker.state, 'half-open')  # 未重开
            # 再 1 次直接成功 → 连续 2 次 → CLOSED
            self.agent.analysis_backend.analyze.side_effect = None
            self.agent.analysis_backend.analyze.return_value = _success_result()
            self.agent.process_log(_raw_message('e5'))
            self.assertEqual(self.agent.dify_breaker.state, 'closed')
        # 熔断未回到 OPEN,失败计数清零
        self.assertEqual(self.agent.dify_breaker.fail_counter, 0)

    def test_half_open_probe_all_retry_fail_reopens(self) -> None:
        self._trip_to_open()
        _REAL_SLEEP(0.07)  # → HALF_OPEN
        with mock.patch('time.sleep'):
            # 探测:Retry 全耗尽失败(4 次 analyze)→ 最终 failed → 重新 OPEN
            result = self.agent.process_log(_raw_message('e4'))
            self.assertEqual(self.agent.dify_breaker.state, 'open')
            self.assertFalse(result)  # 探测失败进 DLQ
            # 重开是因为"完整探测调用最终失败"计 1 次,不是 Retry 内部 4 次尝试
            self.assertEqual(self.agent.analysis_backend.analyze.call_count, 12 + 4)
            # 紧接下一条仍 OPEN → fallback 降级
            result2 = self.agent.process_log(_raw_message('e5'))
            self.assertTrue(result2)

    def test_half_open_probe_first_success_no_retry(self) -> None:
        self._trip_to_open()
        _REAL_SLEEP(0.07)  # → HALF_OPEN
        self.agent.analysis_backend.analyze.return_value = _success_result()
        with mock.patch('time.sleep'):
            # 探测首次直接 success(无需 Retry)→ 计成功
            self.agent.process_log(_raw_message('e4'))
            self.assertEqual(self.agent.dify_breaker.state, 'half-open')
            # 第 2 次成功 → CLOSED
            self.agent.process_log(_raw_message('e5'))
            self.assertEqual(self.agent.dify_breaker.state, 'closed')

    def test_fallback_never_called_in_half_open(self) -> None:
        self._trip_to_open()
        _REAL_SLEEP(0.07)  # → HALF_OPEN
        self.agent.analysis_backend.analyze.return_value = _success_result()
        with mock.patch('time.sleep'):
            # HALF_OPEN 探测走真实 analyze,build_degraded_result 不应被调用
            with mock.patch('services.agent.main.build_degraded_result') as fb_mock:
                self.agent.process_log(_raw_message('e4'))
                fb_mock.assert_not_called()
            self.assertEqual(self.agent.dify_breaker.state, 'half-open')


class RiskScoreContractTests(unittest.TestCase):
    """验证 risk_score=0 消费者契约:降级唯一标识是 raw_response.degraded(7.3,4 用例)。"""

    def test_degraded_result_risk_score_is_zero(self) -> None:
        from services.agent.preprocessor import build_degraded_result
        result = build_degraded_result(_raw_message())
        self.assertEqual(result.risk_score, 0)  # NOT NULL 占位,非"低风险"

    def test_degraded_report_has_degraded_flag(self) -> None:
        from services.agent.preprocessor import build_report_record, build_degraded_result
        raw = _raw_message()
        record = build_report_record(raw, build_degraded_result(raw))
        # 降级唯一可靠标识:raw_response.degraded=True + reason=circuit_open
        self.assertTrue(record['raw_response'].get('degraded'))
        self.assertEqual(record['raw_response'].get('reason'), 'circuit_open')

    def test_degraded_report_risk_score_not_safe_as_low_risk(self) -> None:
        from services.agent.preprocessor import build_report_record, build_degraded_result
        raw = _raw_message()
        record = build_report_record(raw, build_degraded_result(raw))
        # 契约断言:降级报告 risk_score==0,但必须先查 raw_response.degraded 排除
        # 若消费者 WHERE risk_score < 30 未排除 degraded,会把本条误纳入低风险统计
        self.assertEqual(record['risk_score'], 0)
        self.assertTrue(record['raw_response'].get('degraded'))
        # 模拟错误查询:risk_score < 30 会命中降级报告 → 契约违反提醒
        caught_by_naive_query = record['risk_score'] < 30
        excluded_by_contract = record['raw_response'].get('degraded') is True
        self.assertTrue(
            caught_by_naive_query and excluded_by_contract,
            '降级报告会被 risk_score<30 查询误纳,消费者必须先排除 raw_response.degraded=True'
        )

    def test_normal_report_risk_score_zero_is_valid(self) -> None:
        from services.agent.preprocessor import build_report_record
        # 正常成功报告 risk_score=0 是合法值(LLM 可能返回 0 分),非降级
        result = AnalysisResult(
            status='success', log_id='e1', risk_level='low', risk_score=0,
            raw_response={'data': {}},
        )
        record = build_report_record(_raw_message(), result)
        self.assertEqual(record['risk_score'], 0)
        # 正常报告无 degraded 标记 → risk_score=0 是真实评分,非降级
        self.assertFalse(record['raw_response'].get('degraded'))


if __name__ == '__main__':
    unittest.main()
