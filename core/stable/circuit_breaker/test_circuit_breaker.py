"""熔断器模块测试(unittest)。

运行方式(项目根目录):
    python -m unittest core.stable.circuit_breaker.test_circuit_breaker -v
"""

import time
import unittest

from core.stable.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
)


class _Probe:
    """可控行为的探针函数封装。"""

    def __init__(self, result='ok', error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


class CircuitBreakerConfigTests(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = CircuitBreakerConfig()
        self.assertEqual(cfg.fail_max, 5)
        self.assertEqual(cfg.reset_timeout, 30.0)
        self.assertEqual(cfg.success_threshold, 2)
        self.assertEqual(cfg.exceptions, (Exception,))
        self.assertIsNone(cfg.on_state_change)
        self.assertEqual(cfg.name, 'circuit_breaker')

    def test_negative_fail_max_raises(self) -> None:
        with self.assertRaises(ValueError):
            CircuitBreakerConfig(fail_max=-1)

    def test_zero_reset_timeout_raises(self) -> None:
        with self.assertRaises(ValueError):
            CircuitBreakerConfig(reset_timeout=0)

    def test_success_threshold_below_one_raises(self) -> None:
        with self.assertRaises(ValueError):
            CircuitBreakerConfig(success_threshold=0)

    def test_empty_exceptions_raises(self) -> None:
        with self.assertRaises(ValueError):
            CircuitBreakerConfig(exceptions=())

    def test_non_exception_type_raises(self) -> None:
        with self.assertRaises(ValueError):
            CircuitBreakerConfig(exceptions=(int,))


class CircuitBreakerBasicTests(unittest.TestCase):
    def test_succeeds_on_first_call(self) -> None:
        fn = _Probe('ok')
        cb = CircuitBreaker(fail_max=2, reset_timeout=60)
        self.assertEqual(cb.call(fn), 'ok')
        self.assertEqual(fn.calls, 1)
        self.assertEqual(cb.state, 'closed')

    def test_fail_counter_increases_without_trip(self) -> None:
        fn = _Probe(error=ValueError('boom'))
        cb = CircuitBreaker(fail_max=3, reset_timeout=60)
        for _ in range(2):
            with self.assertRaises(ValueError):
                cb.call(fn)
        self.assertEqual(cb.fail_counter, 2)
        self.assertEqual(cb.state, 'closed')

    def test_trip_after_fail_max_failures(self) -> None:
        fn = _Probe(error=ValueError('boom'))
        cb = CircuitBreaker(fail_max=2, reset_timeout=60)
        for _ in range(2):
            with self.assertRaises(ValueError):
                cb.call(fn)
        self.assertEqual(cb.state, 'open')

    def test_open_state_skips_target_function(self) -> None:
        fn = _Probe(error=ValueError('boom'))
        cb = CircuitBreaker(fail_max=1, reset_timeout=60)
        with self.assertRaises(ValueError):
            cb.call(fn)
        self.assertEqual(cb.state, 'open')
        # 熔断打开:不再执行目标函数,抛 CircuitOpenError
        with self.assertRaises(CircuitOpenError):
            cb.call(fn)
        self.assertEqual(fn.calls, 1)  # 第二次调用未执行

    def test_open_returns_fallback(self) -> None:
        fn = _Probe(error=ValueError('boom'))
        cb = CircuitBreaker(fail_max=1, reset_timeout=60)
        with self.assertRaises(ValueError):
            cb.call(fn)
        self.assertEqual(
            cb.call(fn, fallback={'status': 'failed'}), {'status': 'failed'}
        )
        self.assertEqual(fn.calls, 1)  # fallback 不执行目标函数


class CircuitBreakerRecoveryTests(unittest.TestCase):
    def test_recovers_to_closed_after_timeout(self) -> None:
        fn_fail = _Probe(error=ValueError('boom'))
        fn_ok = _Probe('ok')
        cb = CircuitBreaker(fail_max=1, reset_timeout=0.05, success_threshold=1)
        with self.assertRaises(ValueError):
            cb.call(fn_fail)
        self.assertEqual(cb.state, 'open')
        time.sleep(0.07)
        # 冷却到期,放行探测,成功 -> 关闭
        self.assertEqual(cb.call(fn_ok), 'ok')
        self.assertEqual(cb.state, 'closed')

    def test_half_open_requires_success_threshold(self) -> None:
        fn_fail = _Probe(error=ValueError('boom'))
        fn_ok = _Probe('ok')
        cb = CircuitBreaker(fail_max=1, reset_timeout=0.05, success_threshold=2)
        with self.assertRaises(ValueError):
            cb.call(fn_fail)
        time.sleep(0.07)
        self.assertEqual(cb.call(fn_ok), 'ok')   # 第 1 次探测成功
        self.assertEqual(cb.state, 'half-open')  # 仍需 1 次成功才关闭
        self.assertEqual(cb.call(fn_ok), 'ok')
        self.assertEqual(cb.state, 'closed')

    def test_half_open_failure_retrips(self) -> None:
        fn = _Probe(error=ValueError('boom'))
        cb = CircuitBreaker(fail_max=1, reset_timeout=0.05, success_threshold=2)
        with self.assertRaises(ValueError):
            cb.call(fn)
        time.sleep(0.07)
        with self.assertRaises(ValueError):
            cb.call(fn)  # 半开探测失败 -> 重新打开
        self.assertEqual(cb.state, 'open')


class CircuitBreakerResultFailureTests(unittest.TestCase):
    def test_result_failure_counts_and_returns_original(self) -> None:
        fn = _Probe({'status': 'failed'})
        cb = CircuitBreaker(fail_max=3, reset_timeout=60)
        result = cb.call(
            fn, result_is_failure=lambda r: r.get('status') == 'failed'
        )
        self.assertEqual(result, {'status': 'failed'})  # 原样返回
        self.assertEqual(cb.fail_counter, 1)             # 失败已计数
        self.assertEqual(cb.state, 'closed')

    def test_result_failure_trips_breaker(self) -> None:
        fn = _Probe({'status': 'failed'})
        cb = CircuitBreaker(fail_max=1, reset_timeout=60)
        result = cb.call(
            fn, result_is_failure=lambda r: r.get('status') == 'failed'
        )
        self.assertEqual(result, {'status': 'failed'})
        self.assertEqual(cb.state, 'open')  # 恰为第 1 次失败 -> 熔断

    def test_result_success_not_counted(self) -> None:
        fn = _Probe({'status': 'success'})
        cb = CircuitBreaker(fail_max=1, reset_timeout=60)
        result = cb.call(
            fn, result_is_failure=lambda r: r.get('status') == 'failed'
        )
        self.assertEqual(result, {'status': 'success'})
        self.assertEqual(cb.fail_counter, 0)


class CircuitBreakerExceptionFilterTests(unittest.TestCase):
    def test_outside_whitelist_not_counted(self) -> None:
        fn = _Probe(error=TypeError('bad type'))
        cb = CircuitBreaker(fail_max=2, reset_timeout=60, exceptions=(ValueError,))
        with self.assertRaises(TypeError):
            cb.call(fn)
        self.assertEqual(cb.fail_counter, 0)  # 白名单外不计失败
        self.assertEqual(cb.state, 'closed')

    def test_whitelist_exception_counts(self) -> None:
        fn = _Probe(error=ValueError('boom'))
        cb = CircuitBreaker(fail_max=2, reset_timeout=60, exceptions=(ValueError,))
        with self.assertRaises(ValueError):
            cb.call(fn)
        self.assertEqual(cb.fail_counter, 1)


class CircuitBreakerCallbackTests(unittest.TestCase):
    def test_on_state_change_receives_transitions(self) -> None:
        transitions = []
        fn = _Probe(error=ValueError('boom'))
        cb = CircuitBreaker(
            fail_max=1, reset_timeout=0.05, success_threshold=1,
            on_state_change=lambda old, new: transitions.append((old, new)),
        )
        with self.assertRaises(ValueError):
            cb.call(fn)
        self.assertIn(('closed', 'open'), transitions)
        time.sleep(0.07)
        cb.call(_Probe('ok'))
        self.assertIn(('open', 'half-open'), transitions)
        self.assertIn(('half-open', 'closed'), transitions)


class CircuitBreakerDecoratorTests(unittest.TestCase):
    def test_decorator_basic(self) -> None:
        breaker = CircuitBreaker(fail_max=2, reset_timeout=60)
        calls = []

        @breaker
        def work() -> str:
            calls.append(1)
            if len(calls) < 2:
                raise ValueError('flaky')
            return 'done'

        # 熔断器不重试:第 1 次失败直接抛出并计数
        with self.assertRaises(ValueError):
            work()
        self.assertEqual(work(), 'done')  # 第 2 次成功
        self.assertEqual(len(calls), 2)

    def test_decorator_open_raises(self) -> None:
        breaker = CircuitBreaker(fail_max=1, reset_timeout=60)

        @breaker
        def work() -> None:
            raise ValueError('boom')

        with self.assertRaises(ValueError):
            work()
        with self.assertRaises(CircuitOpenError):
            work()


class CircuitBreakerDisabledTests(unittest.TestCase):
    def test_fail_max_zero_disables(self) -> None:
        fn = _Probe(error=ValueError('boom'))
        cb = CircuitBreaker(fail_max=0)
        with self.assertRaises(ValueError):
            cb.call(fn)  # 异常直接传播,不计数
        self.assertEqual(cb.state, 'closed')
        self.assertEqual(cb.fail_counter, 0)
        self.assertEqual(cb.call(_Probe('ok')), 'ok')


if __name__ == '__main__':
    unittest.main()
