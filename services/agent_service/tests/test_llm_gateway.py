"""LLM Gateway P0-6 单元测试(对齐设计 §3.7)。

覆盖:
- 多角色配置(analysis / light)切换
- overrides 形参(workflow 调用方式)向后兼容
- 未知 role / 配置缺失 → LLMConfigError 显式报错(不静默降级)
- fallback 链:主 role 实例化失败 → 走 LLM_FALLBACK_CHAIN 下一 role
- token usage:Recorder 单例 + 聚合统计 + CallbackHandler 解析 llm_output
- 结构化输出重试:解析失败附加错误反馈,非解析异常不重试

运行(项目根目录):
    python -m unittest services.agent_service.tests.test_llm_gateway
"""
import os
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_SERVICE_DIR = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_AGENT_SERVICE_DIR)
for _p in (_AGENT_SERVICE_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class TestLLMConfigAndRouting(unittest.TestCase):
    """角色路由 + 配置缺失显式报错。"""

    def test_get_llm_default_role_is_analysis(self):
        """get_llm() 无参 → role='analysis',行为对齐 v1。"""
        from shared.llm.factory import get_llm
        from shared.config.settings import LLM_CONFIGS
        llm = get_llm()
        # ChatOpenAI 把 model 存在 model_name
        self.assertEqual(llm.model_name, LLM_CONFIGS['analysis']['model'])

    def test_get_llm_role_light_uses_light_model(self):
        """get_llm(role='light') → 用 light 角色的 model。"""
        from shared.llm.factory import get_llm
        from shared.config.settings import LLM_CONFIGS
        llm = get_llm(role='light')
        self.assertEqual(llm.model_name, LLM_CONFIGS['light']['model'])

    def test_get_llm_overrides_apply(self):
        """workflow nodes.py 的调用方式:get_llm(temperature=, model=, ...) overrides。"""
        from shared.llm.factory import get_llm
        llm = get_llm(temperature=0.42, model='custom-model', streaming=False)
        self.assertEqual(llm.model_name, 'custom-model')
        self.assertAlmostEqual(llm.temperature, 0.42)
        # streaming 通过 kwargs 暴露(ChatOpenAI 默认 streaming 字段)
        self.assertFalse(llm.streaming)

    def test_unknown_role_raises_config_error(self):
        """未知 role → LLMConfigError,不静默走默认。"""
        from shared.llm.factory import get_llm
        from shared.llm.exceptions import LLMConfigError
        with self.assertRaises(LLMConfigError) as ctx:
            get_llm(role='nonexistent_role')
        self.assertIn('nonexistent_role', str(ctx.exception))

    def test_missing_api_key_raises_config_error(self):
        """analysis 角色 api_key 缺失 → LLMConfigError,不静默降级。"""
        from shared.llm.factory import get_llm
        from shared.llm.exceptions import LLMConfigError
        from shared.config import settings as settings_module
        original = settings_module.LLM_CONFIGS['analysis']['api_key']
        try:
            settings_module.LLM_CONFIGS['analysis']['api_key'] = ''
            with self.assertRaises(LLMConfigError) as ctx:
                get_llm(role='analysis')
            self.assertIn('api_key', str(ctx.exception))
        finally:
            settings_module.LLM_CONFIGS['analysis']['api_key'] = original


class TestFallbackChain(unittest.TestCase):
    """fallback 链:主 role 实例化失败 → 走下一 role。"""

    def test_fallback_when_primary_runtime_failure(self):
        """主 role 实例化抛非 LLMConfigError → 走 fallback 到 light。"""
        from shared.llm import factory as factory_module
        from shared.llm.openai_compat import OpenAICompatProvider
        from shared.config.settings import LLM_CONFIGS

        # 记录每次 build 调用的 role
        calls: list[str] = []
        original_build = OpenAICompatProvider.build

        def fake_build(self):
            calls.append(self.role)
            if self.role == 'analysis':
                raise RuntimeError('simulated primary failure')
            # light 走真实 build,返回真实 ChatOpenAI
            return original_build(self)

        with patch.object(OpenAICompatProvider, 'build', fake_build):
            llm = factory_module.get_llm(role='analysis')

        self.assertEqual(calls, ['analysis', 'light'])
        self.assertEqual(llm.model_name, LLM_CONFIGS['light']['model'])

    def test_fallback_all_fail_raises_unavailable(self):
        """fallback 链全部失败 → LLMUnavailableError,不返回 None。"""
        from shared.llm import factory as factory_module
        from shared.llm.openai_compat import OpenAICompatProvider
        from shared.llm.exceptions import LLMUnavailableError

        def always_fail(self):
            raise RuntimeError('all providers down')

        with patch.object(OpenAICompatProvider, 'build', always_fail):
            with self.assertRaises(LLMUnavailableError) as ctx:
                factory_module.get_llm(role='analysis')
        self.assertIn('analysis', str(ctx.exception))


class TestTokenUsageRecorder(unittest.TestCase):
    """token usage 单例 + 聚合 + JSONL 落盘。"""

    def test_recorder_is_singleton(self):
        from shared.llm.token_usage import get_token_recorder
        a = get_token_recorder()
        b = get_token_recorder()
        self.assertIs(a, b)

    def test_record_and_aggregate(self):
        """record() 写入 + 聚合统计正确。"""
        from shared.llm.token_usage import (
            TokenUsageRecord, get_token_recorder,
        )
        rec = get_token_recorder()
        before = rec.get_summary()
        rec.record(TokenUsageRecord(
            ts=0.0, role='analysis', model='m1',
            prompt_tokens=10, completion_tokens=5, total_tokens=15, ok=True,
        ))
        rec.record(TokenUsageRecord(
            ts=0.0, role='analysis', model='m1',
            prompt_tokens=20, completion_tokens=8, total_tokens=28, ok=False,
            error='boom',
        ))
        after = rec.get_summary()
        self.assertEqual(after['total_calls'] - before['total_calls'], 2)
        self.assertEqual(after['failed_calls'] - before['failed_calls'], 1)
        self.assertEqual(
            after['total_prompt_tokens'] - before['total_prompt_tokens'], 30
        )
        self.assertEqual(
            after['total_completion_tokens'] - before['total_completion_tokens'], 13
        )
        # by_role 增量
        delta_role = {
            k: (after['by_role'].get(k, {}) if k in before['by_role']
                else after['by_role'][k])
            for k in after['by_role']
        }
        self.assertIn('analysis', after['by_role'])
        self.assertGreaterEqual(after['by_role']['analysis']['calls'], 2)

    def test_callback_handler_extracts_tokens_from_llm_output(self):
        """CallbackHandler 从 response.llm_output.token_usage 提取 token 数。"""
        from shared.llm.token_usage import (
            TokenUsageCallbackHandler, get_token_recorder,
        )
        handler = TokenUsageCallbackHandler(role='analysis', model='m1')
        rec = get_token_recorder()
        before = rec.get_summary()

        # 模拟 on_llm_start → on_llm_end 流程
        handler.on_chat_model_start(serialized={}, messages=[], run_id='rid-1')
        response = SimpleNamespace(
            llm_output={'token_usage': {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'total_tokens': 150,
            }}
        )
        handler.on_llm_end(response, run_id='rid-1')

        after = rec.get_summary()
        delta_total = after['total_tokens'] - before['total_tokens']
        self.assertEqual(delta_total, 150)
        delta_prompt = after['total_prompt_tokens'] - before['total_prompt_tokens']
        self.assertEqual(delta_prompt, 100)

    def test_callback_handler_handles_missing_token_usage(self):
        """response 无 token_usage 字段时(部分 provider 不返回)不抛错。"""
        from shared.llm.token_usage import (
            TokenUsageCallbackHandler, get_token_recorder,
        )
        handler = TokenUsageCallbackHandler(role='light', model='m2')
        rec = get_token_recorder()
        before = rec.get_summary()
        handler.on_chat_model_start(serialized={}, messages=[], run_id='rid-2')
        response = SimpleNamespace(llm_output={})
        handler.on_llm_end(response, run_id='rid-2')
        after = rec.get_summary()
        # 调用计数 +1 但 token 增量为 0
        self.assertEqual(after['total_calls'] - before['total_calls'], 1)
        self.assertEqual(after['total_tokens'] - before['total_tokens'], 0)

    def test_callback_handler_records_errors(self):
        """on_llm_error 记录失败调用。"""
        from shared.llm.token_usage import (
            TokenUsageCallbackHandler, get_token_recorder,
        )
        handler = TokenUsageCallbackHandler(role='analysis', model='m1')
        rec = get_token_recorder()
        before = rec.get_summary()
        handler.on_chat_model_start(serialized={}, messages=[], run_id='rid-3')
        handler.on_llm_error(RuntimeError('boom'), run_id='rid-3')
        after = rec.get_summary()
        self.assertEqual(after['failed_calls'] - before['failed_calls'], 1)


class TestStructuredOutputRetry(unittest.TestCase):
    """结构化输出解析失败重试。"""

    def _make_pydantic_schema(self):
        from pydantic import BaseModel, Field

        class _S(BaseModel):
            answer: str = Field(description='the answer')
            confidence: float
        return _S

    def test_succeed_first_try_no_retry(self):
        """首次调用成功 → 直接返回,无重试。"""
        from pydantic import BaseModel, Field

        class Schema(BaseModel):
            answer: str
            confidence: float

        from shared.llm.retry import invoke_structured_with_retry

        # mock llm_structured,记录调用次数
        call_count = {'n': 0}

        class FakeStructured:
            async def ainvoke(self, messages):
                call_count['n'] += 1
                return Schema(answer='ok', confidence=0.9)

        result = __import__('asyncio').run(
            invoke_structured_with_retry(
                FakeStructured(), [], Schema, max_retries=2,
            )
        )
        self.assertEqual(call_count['n'], 1)
        self.assertEqual(result.answer, 'ok')

    def test_retries_on_validation_error_with_feedback(self):
        """ValidationError → 附加错误反馈重试,第 N 次成功。"""
        from pydantic import BaseModel, Field

        class Schema(BaseModel):
            answer: str
            confidence: float

        from shared.llm.retry import invoke_structured_with_retry

        call_count = {'n': 0}

        class FakeStructured:
            async def ainvoke(self, messages):
                call_count['n'] += 1
                if call_count['n'] == 1:
                    # 模拟 schema 解析失败
                    from pydantic import ValidationError
                    raise ValidationError.from_exception_data(
                        'Schema', [{'type': 'missing', 'loc': ('answer',), 'input': {}}]
                    )
                # 第二次成功;且应能看到追加的反馈消息
                # 检查 messages 末尾有 SystemMessage 含 '上次输出解析失败'
                last = messages[-1]
                assert '上次输出解析失败' in last.content, \
                    f"反馈消息未追加: {last.content}"
                return Schema(answer='retried', confidence=0.5)

        result = __import__('asyncio').run(
            invoke_structured_with_retry(
                FakeStructured(), [], Schema, max_retries=2,
            )
        )
        self.assertEqual(call_count['n'], 2)
        self.assertEqual(result.answer, 'retried')

    def test_raises_after_max_retries(self):
        """超过 max_retries 次仍失败 → 抛最后一次 ValidationError。"""
        from pydantic import BaseModel, Field, ValidationError

        class Schema(BaseModel):
            answer: str
            confidence: float

        from shared.llm.retry import invoke_structured_with_retry

        class FakeStructured:
            async def ainvoke(self, messages):
                raise ValidationError.from_exception_data(
                    'Schema', [{'type': 'missing', 'loc': ('answer',), 'input': {}}]
                )

        with self.assertRaises(ValidationError):
            __import__('asyncio').run(
                invoke_structured_with_retry(
                    FakeStructured(), [], Schema, max_retries=1,
                )
            )

    def test_non_parse_error_not_retried(self):
        """非解析异常(网络/超时)不重试,直接抛。"""
        from pydantic import BaseModel, Field

        class Schema(BaseModel):
            answer: str

        from shared.llm.retry import invoke_structured_with_retry

        call_count = {'n': 0}

        class FakeStructured:
            async def ainvoke(self, messages):
                call_count['n'] += 1
                raise RuntimeError('network down')

        with self.assertRaises(RuntimeError):
            __import__('asyncio').run(
                invoke_structured_with_retry(
                    FakeStructured(), [], Schema, max_retries=3,
                )
            )
        self.assertEqual(call_count['n'], 1)


if __name__ == '__main__':
    unittest.main()
