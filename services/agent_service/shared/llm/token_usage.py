"""Token usage 统计(轻量 tracing 的一部分,对齐设计 §3.7 / §3.9)。

设计要点:
- 每次 LLM 调用记录 prompt/completion/total tokens + role + model + 延迟 + 错误
- 进程内聚合 + JSON Lines 文件落盘(logs/token_usage.jsonl)
- 通过 LangChain BaseCallbackHandler 钩到 LLM 调用,不侵入业务代码
- 单例:全进程一个 Recorder,所有 LLM 调用共享

不引入 Redis / 外部存储:这是 P0 轻量 tracing,P2 Langfuse 才考虑外部存储。
"""
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)

# agent_service 根目录:shared/llm/token_usage.py → 上三级
_AGENT_SERVICE_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = _AGENT_SERVICE_ROOT / "logs"
TOKEN_USAGE_LOG = LOG_DIR / "token_usage.jsonl"


@dataclass
class TokenUsageRecord:
    """单次 LLM 调用的 token 用量记录。"""
    ts: float  # epoch seconds
    role: str  # 'analysis' / 'light' / fallback 时的实际 role
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    ok: bool = True
    error: Optional[str] = None
    # 用于追踪 LLM 调用上下文(节点名/agent 名);由 callback 的 run_id 关联
    run_id: Optional[str] = None


@dataclass
class TokenUsageSummary:
    """聚合统计快照。"""
    total_calls: int = 0
    ok_calls: int = 0
    failed_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    by_role: dict = field(default_factory=dict)  # role -> {calls, prompt, completion, total}


class TokenUsageRecorder:
    """进程内 token 用量记录器(单例)。

    线程安全(锁保护内部聚合);每次 record 写一行 JSONL 到 logs/token_usage.jsonl。
    聚合统计通过 get_summary() 取快照。
    """
    _instance: Optional["TokenUsageRecorder"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "TokenUsageRecorder":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._records: list[TokenUsageRecord] = []
        self._summary = TokenUsageSummary()
        self._file_lock = threading.Lock()
        # 日志目录懒创建:首次写时建
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("无法创建 logs 目录 %s: %s", LOG_DIR, e)

    def record(self, record: TokenUsageRecord) -> None:
        """记录一次调用:聚合 + 落盘 JSONL。"""
        with self._file_lock:
            self._records.append(record)
            self._summary.total_calls += 1
            if record.ok:
                self._summary.ok_calls += 1
            else:
                self._summary.failed_calls += 1
            self._summary.total_prompt_tokens += record.prompt_tokens
            self._summary.total_completion_tokens += record.completion_tokens
            self._summary.total_tokens += record.total_tokens

            role_stat = self._summary.by_role.setdefault(
                record.role,
                {"calls": 0, "ok": 0, "failed": 0,
                 "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            )
            role_stat["calls"] += 1
            if record.ok:
                role_stat["ok"] += 1
            else:
                role_stat["failed"] += 1
            role_stat["prompt_tokens"] += record.prompt_tokens
            role_stat["completion_tokens"] += record.completion_tokens
            role_stat["total_tokens"] += record.total_tokens

            # 追加写一行 JSONL;失败不抛异常,不阻塞业务
            try:
                with open(TOKEN_USAGE_LOG, "a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
            except OSError as e:
                logger.warning("写入 token_usage 日志失败 %s: %s", TOKEN_USAGE_LOG, e)

    def get_summary(self) -> dict:
        """返回聚合统计的快照(深拷贝避免外部修改)。"""
        with self._file_lock:
            return {
                "total_calls": self._summary.total_calls,
                "ok_calls": self._summary.ok_calls,
                "failed_calls": self._summary.failed_calls,
                "total_prompt_tokens": self._summary.total_prompt_tokens,
                "total_completion_tokens": self._summary.total_completion_tokens,
                "total_tokens": self._summary.total_tokens,
                "by_role": {k: dict(v) for k, v in self._summary.by_role.items()},
                "log_file": str(TOKEN_USAGE_LOG),
            }


def get_token_recorder() -> TokenUsageRecorder:
    """获取全局 token usage 记录器(单例)。"""
    return TokenUsageRecorder()


class TokenUsageCallbackHandler(BaseCallbackHandler):
    """LangChain callback:从 LLM 响应里抓 token usage 入 Recorder。

    挂在 ChatOpenAI 构造时(callbacks=[handler]):
    - on_llm_start: 记录起始时间
    - on_llm_end: 解析 response.llm_output['token_usage'] 入 Recorder
    - on_llm_error: 记录失败原因 + 耗时

    用 threading.local 保存 per-run 起始时间,支持并发。
    """
    def __init__(self, role: str, model: str):
        self.role = role
        self.model = model
        self._start_times = threading.local()

    def _get_start(self, run_id: str) -> float:
        if not hasattr(self._start_times, "map"):
            self._start_times.map = {}
        return self._start_times.map.get(run_id, 0.0)

    def _set_start(self, run_id: str, ts: float) -> None:
        if not hasattr(self._start_times, "map"):
            self._start_times.map = {}
        self._start_times.map[run_id] = ts

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):
        self._set_start(str(run_id), time.time())

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self._set_start(str(run_id), time.time())

    def on_llm_end(self, response, *, run_id, **kwargs):
        start = self._get_start(str(run_id))
        latency_ms = (time.time() - start) * 1000 if start else 0.0
        # 解析 token usage:OpenAI 兼容厂商走 llm_output.token_usage
        prompt_tokens = completion_tokens = total_tokens = 0
        llm_output = getattr(response, "llm_output", None) or {}
        token_usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
        if token_usage:
            prompt_tokens = int(token_usage.get("prompt_tokens", 0) or 0)
            completion_tokens = int(token_usage.get("completion_tokens", 0) or 0)
            total_tokens = int(token_usage.get("total_tokens", 0) or 0)

        get_token_recorder().record(TokenUsageRecord(
            ts=time.time(),
            role=self.role,
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            ok=True,
            run_id=str(run_id),
        ))

    def on_llm_error(self, error, *, run_id, **kwargs):
        start = self._get_start(str(run_id))
        latency_ms = (time.time() - start) * 1000 if start else 0.0
        get_token_recorder().record(TokenUsageRecord(
            ts=time.time(),
            role=self.role,
            model=self.model,
            latency_ms=latency_ms,
            ok=False,
            error=type(error).__name__ + ": " + str(error)[:200],
            run_id=str(run_id),
        ))
