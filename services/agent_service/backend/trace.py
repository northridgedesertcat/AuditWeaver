"""轻量 Tracing:LangGraph/LangChain callback 落盘 JSONL(对齐 §3.9)。

设计要点:
- 配置驱动:``AE_TRACE_LOG`` 环境变量指定日志路径;未配置则跳过(对齐
  §3.9 "配置缺失跳过不报错")。路径配置了但不可写则构造时显式报错
  (对齐项目"配置缺失显式报错不静默"原则)。
- 全链路可观测:捕获节点 on_chain_start/end、LLM on_llm_start/end(含
  token usage)、工具 on_tool_start/end,每条一行 JSON。面试可逐行讲解
  "节点时序 + LLM prompt/completion/token + 工具调用"。
- 进程内单例 + 文件 append 加锁,多请求共用一个 handler 实例(handler
  无状态字段,仅写文件),适合 FastAPI 单进程多请求。
- 不上 Langfuse 自托管(P2 扩展点);本文件即最小闭环可观测。
"""
import json
import os
import threading
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from common.env import get_env


class FileTraceCallback(BaseCallbackHandler):
    """落盘 JSONL 的 LangChain callback handler。

    每个事件一行 JSON,字段:
    - ts: 毫秒时间戳
    - run_id: LangChain run id(同一次 chain/tool/llm 调用 start 与 end 配对)
    - event: 事件名(on_chain_start/on_chain_end/on_llm_start/on_llm_end/
      on_tool_start/on_tool_end/*_error)
    - name: 节点/模型/工具名(节点名从 metadata.langgraph_node 取,对齐
      langgraph 0.2.x 的 astream_events 契约)
    - extra: 事件特定字段(prompt_preview/completion_preview/tokens/
      output_keys/error 等,统一截断避免日志膨胀)

    线程安全:单文件 append 加锁;同步 handler,Little I/O,Little state。
    """

    def __init__(self, log_path: str) -> None:
        self.log_path = log_path
        self._lock = threading.Lock()
        # 确保目录存在 + 触摸文件,立刻暴露权限/路径问题
        d = os.path.dirname(log_path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            pass  # 触摸,不可写则此处抛错(显式报错,不静默)

    def _write(self, record: dict) -> None:
        record["ts"] = int(time.time() * 1000)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    # ---- chain (含 LangGraph 节点)----
    def on_chain_start(
        self, serialized: dict, inputs: Any, *, run_id=None, **kwargs
    ) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name") or "chain"
        self._write({
            "event": "on_chain_start",
            "run_id": run_id,
            "name": name,
            "extra": {"inputs_type": type(inputs).__name__},
        })

    def on_chain_end(self, outputs: Any, *, run_id=None, **kwargs) -> None:
        # 节点名优先从 metadata.langgraph_node 取(astream_events v2 契约)
        metadata = kwargs.get("metadata") or {}
        name = metadata.get("langgraph_node") or kwargs.get("name") or "chain"
        out_keys = None
        if isinstance(outputs, dict):
            out_keys = list(outputs.keys())
        self._write({
            "event": "on_chain_end",
            "run_id": run_id,
            "name": name,
            "extra": {"output_keys": out_keys},
        })

    def on_chain_error(self, error, *, run_id=None, **kwargs) -> None:
        metadata = kwargs.get("metadata") or {}
        name = metadata.get("langgraph_node") or kwargs.get("name") or "chain"
        self._write({
            "event": "on_chain_error",
            "run_id": run_id,
            "name": name,
            "extra": {"error": repr(error)[:300]},
        })

    # ---- LLM ----
    def on_llm_start(
        self, serialized, prompts, *, run_id=None, **kwargs
    ) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name") or "llm"
        prompt_preview = ""
        try:
            if prompts and isinstance(prompts[0], list):
                prompt_preview = str(prompts[0][-1])[:200]
            elif prompts:
                prompt_preview = str(prompts[0])[:200]
        except Exception:
            prompt_preview = ""
        self._write({
            "event": "on_llm_start",
            "run_id": run_id,
            "name": name,
            "extra": {"prompt_preview": prompt_preview},
        })

    def on_llm_end(self, response: LLMResult, *, run_id=None, **kwargs) -> None:
        name = kwargs.get("name") or "llm"
        # token usage(兼容 OpenAI / Anthropic / 自建 token_usage 字段名)
        tokens: dict = {}
        try:
            llm_output = response.llm_output or {}
            tu = llm_output.get("token_usage") or llm_output.get("usage") or {}
            if tu:
                tokens = {
                    "prompt_tokens": tu.get("prompt_tokens")
                    or tu.get("input_tokens"),
                    "completion_tokens": tu.get("completion_tokens")
                    or tu.get("output_tokens"),
                    "total_tokens": tu.get("total_tokens"),
                }
        except Exception:
            pass
        # completion 预览
        completion_preview = ""
        try:
            if response.generations and response.generations[0]:
                gen = response.generations[0][0]
                completion_preview = (getattr(gen, "text", "") or "")[:200]
        except Exception:
            pass
        self._write({
            "event": "on_llm_end",
            "run_id": run_id,
            "name": name,
            "extra": {"tokens": tokens, "completion_preview": completion_preview},
        })

    def on_llm_error(self, error, *, run_id=None, **kwargs) -> None:
        self._write({
            "event": "on_llm_error",
            "run_id": run_id,
            "name": kwargs.get("name") or "llm",
            "extra": {"error": repr(error)[:300]},
        })

    # ---- tool ----
    def on_tool_start(
        self, serialized, input_str, *, run_id=None, **kwargs
    ) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name") or "tool"
        self._write({
            "event": "on_tool_start",
            "run_id": run_id,
            "name": name,
            "extra": {"input": str(input_str)[:200]},
        })

    def on_tool_end(self, output, *, run_id=None, **kwargs) -> None:
        name = kwargs.get("name") or "tool"
        self._write({
            "event": "on_tool_end",
            "run_id": run_id,
            "name": name,
            "extra": {"output_preview": str(output)[:200]},
        })

    def on_tool_error(self, error, *, run_id=None, **kwargs) -> None:
        self._write({
            "event": "on_tool_error",
            "run_id": run_id,
            "name": kwargs.get("name") or "tool",
            "extra": {"error": repr(error)[:300]},
        })


_trace_callback: FileTraceCallback | None = None
_trace_lock = threading.Lock()


def get_trace_callback() -> FileTraceCallback | None:
    """返回进程级 ``FileTraceCallback`` 单例(若启用)。

    - ``AE_TRACE_LOG`` 未设置 → 返回 None(跳过 tracing,不报错,对齐 §3.9)
    - ``AE_TRACE_LOG`` 设置但路径不可写 → 构造时抛错(显式报错,不静默)

    返回 None 时调用方应跳过(不传 callbacks 到 graph config)。
    """
    global _trace_callback
    if _trace_callback is not None:
        return _trace_callback
    with _trace_lock:
        if _trace_callback is not None:
            return _trace_callback
        log_path = get_env("AE_TRACE_LOG", "")
        if not log_path:
            return None
        _trace_callback = FileTraceCallback(log_path)
        return _trace_callback


def reset_trace_callback() -> None:
    """重置单例(测试用:切换 env 后重新初始化)。"""
    global _trace_callback
    with _trace_lock:
        _trace_callback = None
