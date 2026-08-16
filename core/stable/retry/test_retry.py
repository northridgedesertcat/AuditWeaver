"""线性退避重试模块测试(unittest)。

运行方式(项目根目录):
    python -m unittest core.stable.retry.test_retry -v
"""

import unittest
from unittest import mock

from core.stable.retry import Retry, RetryConfig, retry


class _Flaky:
    """可控失败次数的探针函数封装。"""

    def __init__(self, fail_times: int, error: Exception = ValueError('boom')):
        self.fail_times = fail_times
        self.error = error
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.error
        return 'ok'


class RetryConfigTests(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = RetryConfig()
        self.assertEqual(cfg.max_retries, 3)
        self.assertEqual(cfg.base_delay, 1.0)
        self.assertEqual(cfg.max_delay, 10.0)
        self.assertEqual(cfg.exceptions, (Exception,))
        self.assertIsNone(cfg.on_retry)
        self.assertEqual(cfg.jitter, 0.0)

    def test_negative_max_retries_raises(self) -> None:
        with self.assertRaises(ValueError):
            RetryConfig(max_retries=-1)

    def test_negative_base_delay_raises(self) -> None:
        with self.assertRaises(ValueError):
            RetryConfig(base_delay=-0.1)

    def test_max_delay_less_than_base_raises(self) -> None:
        with self.assertRaises(ValueError):
            RetryConfig(base_delay=5.0, max_delay=1.0)

    def test_jitter_out_of_range_raises(self) -> None:
        with self.assertRaises(ValueError):
            RetryConfig(jitter=1.0)
        with self.assertRaises(ValueError):
            RetryConfig(jitter=-0.1)

    def test_empty_exceptions_raises(self) -> None:
        with self.assertRaises(ValueError):
            RetryConfig(exceptions=())

    def test_non_exception_type_raises(self) -> None:
        with self.assertRaises(ValueError):
            RetryConfig(exceptions=(int,))


class RetrySuccessTests(unittest.TestCase):
    def test_succeeds_on_first_call(self) -> None:
        fn = _Flaky(fail_times=0)
        self.assertEqual(Retry(max_retries=3, base_delay=0).call(fn), 'ok')
        self.assertEqual(fn.calls, 1)

    def test_succeeds_after_two_failures(self) -> None:
        fn = _Flaky(fail_times=2)
        self.assertEqual(Retry(max_retries=3, base_delay=0).call(fn), 'ok')
        self.assertEqual(fn.calls, 3)

    def test_max_retries_zero_means_no_retry(self) -> None:
        fn = _Flaky(fail_times=1)
        with self.assertRaises(ValueError):
            Retry(max_retries=0, base_delay=0).call(fn)
        self.assertEqual(fn.calls, 1)

    def test_exhausted_reraises_original_exception_instance(self) -> None:
        error = ValueError('boom')
        fn = _Flaky(fail_times=99, error=error)
        with self.assertRaises(ValueError) as ctx:
            Retry(max_retries=3, base_delay=0).call(fn)
        self.assertIs(ctx.exception, error)  # 重抛原异常实例,非 RetryError 包装
        self.assertEqual(fn.calls, 4)  # 首次 + 3 次重试


class RetryExceptionFilterTests(unittest.TestCase):
    def test_outside_whitelist_raises_immediately(self) -> None:
        fn = _Flaky(fail_times=5, error=TypeError('bad type'))
        with self.assertRaises(TypeError):
            Retry(max_retries=3, base_delay=0,
                  exceptions=(ValueError,)).call(fn)
        self.assertEqual(fn.calls, 1)  # 白名单外,不重试

    def test_subclass_matches_whitelist(self) -> None:
        class _ChildError(ValueError):
            pass

        fn = _Flaky(fail_times=1, error=_ChildError('child'))
        self.assertEqual(
            Retry(max_retries=3, base_delay=0,
                  exceptions=(ValueError,)).call(fn), 'ok')
        self.assertEqual(fn.calls, 2)


class RetryCallbackTests(unittest.TestCase):
    def test_on_retry_receives_attempt_exception_delay(self) -> None:
        received = []
        fn = _Flaky(fail_times=3)
        with mock.patch('time.sleep') as mock_sleep:
            Retry(max_retries=3, base_delay=1.0, max_delay=10.0,
                  on_retry=lambda a, e, d: received.append((a, type(e).__name__, d)),
                  ).call(fn)

        # 线性退避:1s -> 2s -> 3s
        self.assertEqual([d for _, _, d in received], [1.0, 2.0, 3.0])
        # attempt 为本次重试序号(1 起)
        self.assertEqual([a for a, _, _ in received], [1, 2, 3])
        self.assertEqual(mock_sleep.call_args_list,
                         [mock.call(1.0), mock.call(2.0), mock.call(3.0)])

    def test_default_logger_emits_warning_on_retry(self) -> None:
        fn = _Flaky(fail_times=1)
        with mock.patch('time.sleep'), mock.patch('core.stable.retry.retry.logging.Logger.warning') as warn:
            Retry(max_retries=1, base_delay=0).call(fn)
        warn.assert_called_once()

    def test_delay_capped_by_max_delay(self) -> None:
        fn = _Flaky(fail_times=4)
        with mock.patch('time.sleep') as mock_sleep:
            Retry(max_retries=4, base_delay=4.0, max_delay=10.0).call(fn)
        # 4s -> 8s -> 10s(封顶)-> 10s(封顶)
        self.assertEqual(mock_sleep.call_args_list,
                         [mock.call(4.0), mock.call(8.0), mock.call(10.0), mock.call(10.0)])


class RetryJitterTests(unittest.TestCase):
    def test_jitter_adds_random_wait(self) -> None:
        fn = _Flaky(fail_times=3)
        with mock.patch('time.sleep') as mock_sleep:
            Retry(max_retries=3, base_delay=1.0, jitter=0.5).call(fn)

        sleeps = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertEqual(len(sleeps), 3)
        # 抖动区间:[线性, 线性 + base_delay × jitter)
        for n, s in zip(range(1, 4), sleeps):
            self.assertGreaterEqual(s, float(n))
            self.assertLess(s, n + 0.5)


class RetryDecoratorTests(unittest.TestCase):
    def test_decorator_basic(self) -> None:
        @retry(max_retries=2, base_delay=0)
        def work() -> str:
            return 'done'

        self.assertEqual(work(), 'done')

    def test_decorator_retries(self) -> None:
        calls = []

        @retry(max_retries=2, base_delay=0)
        def work() -> str:
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError('flaky')
            return 'done'

        self.assertEqual(work(), 'done')
        self.assertEqual(len(calls), 3)

    def test_decorator_preserves_function_metadata(self) -> None:
        @retry(max_retries=1, base_delay=0)
        def work() -> str:
            """docstring"""
            return 'done'

        self.assertEqual(work.__name__, 'work')
        self.assertEqual(work.__doc__, 'docstring')


class RetryPassthroughTests(unittest.TestCase):
    def test_extra_kwargs_passed_to_tenacity(self) -> None:
        from tenacity import retry_if_exception_type

        r = Retry(max_retries=2, retry=retry_if_exception_type(ValueError))
        kwargs = r._build_tenacity_kwargs()
        # 透传参数应出现在 Tenacity kwargs 中
        self.assertIn('retry', kwargs)
        # 项目参数映射保留
        self.assertIn('stop', kwargs)
        self.assertIn('wait', kwargs)
        self.assertTrue(kwargs['reraise'])


class RetryThreadSafetyTests(unittest.TestCase):
    def test_concurrent_calls_are_independent(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        def probe(seed: int) -> int:
            fn = _Flaky(fail_times=seed % 3)
            Retry(max_retries=3, base_delay=0).call(fn)
            return fn.calls

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(probe, range(8)))
        # 每个结果在 [1, 4] 区间,且无跨线程串扰
        for r in results:
            self.assertIn(r, range(1, 5))


if __name__ == '__main__':
    unittest.main()
