"""工具调用审计(对齐设计 §3.6 + §3.9 轻量 tracing)。

每次工具调用记录:工具名 / 入参 / 出参摘要 / ok / 耗时 / 错误 / source_ids,
进程内聚合 + JSONL 落盘(logs/tool_audit.jsonl),不引入外部存储(P2 Langfuse 才考虑)。

设计要点:
- 单例:全进程一个 Recorder,所有工具调用共享
- 线程安全:锁保护内部聚合
- 不阻塞业务:写盘失败仅 warning,不抛异常
- 出参摘要:避免完整 data 撑爆日志(默认截断到 2KB)
"""
import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# agent_service 根目录:shared/tools/audit.py → 上三级
_AGENT_SERVICE_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = _AGENT_SERVICE_ROOT / "logs"
TOOL_AUDIT_LOG = LOG_DIR / "tool_audit.jsonl"

# 单条 audit data 摘要最大字符数(超出截断 + ...[truncated])
MAX_DATA_SUMMARY_LEN = 2000


def _truncate_for_log(value: Any, max_len: int = MAX_DATA_SUMMARY_LEN) -> str:
    """把任意值转 str 并截断,避免单条 audit 过长。"""
    try:
        s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "...[truncated]"
    return s


@dataclass
class ToolAuditRecord:
    """单次工具调用审计记录。"""
    ts: float  # epoch seconds
    tool_name: str
    args: dict  # 入参(原始)
    ok: bool
    duration_ms: float
    error: Optional[str] = None
    error_type: Optional[str] = None
    source_ids: list[str] = field(default_factory=list)
    data_summary: Optional[str] = None  # 出参摘要(截断后)
    # 调用方上下文(节点名/agent 名);由 wrapper 调用时传入,可空
    caller: Optional[str] = None
    # 重试次数(0=首次成功,>0=重试过)
    retry_count: int = 0


@dataclass
class ToolAuditSummary:
    """聚合统计快照。"""
    total_calls: int = 0
    ok_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0.0
    by_tool: dict = field(default_factory=dict)  # tool_name -> {calls, ok, failed, total_ms}


class ToolAuditRecorder:
    """进程内工具调用审计记录器(单例)。

    线程安全;每次 record 写一行 JSONL 到 logs/tool_audit.jsonl。
    """
    _instance: Optional["ToolAuditRecorder"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ToolAuditRecorder":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._records: list[ToolAuditRecord] = []
        self._summary = ToolAuditSummary()
        self._file_lock = threading.Lock()
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("无法创建 logs 目录 %s: %s", LOG_DIR, e)

    def record(self, record: ToolAuditRecord) -> None:
        """记录一次工具调用:聚合 + 落盘 JSONL。"""
        with self._file_lock:
            self._records.append(record)
            self._summary.total_calls += 1
            if record.ok:
                self._summary.ok_calls += 1
            else:
                self._summary.failed_calls += 1
            self._summary.total_duration_ms += record.duration_ms

            tool_stat = self._summary.by_tool.setdefault(
                record.tool_name,
                {"calls": 0, "ok": 0, "failed": 0, "total_ms": 0.0},
            )
            tool_stat["calls"] += 1
            if record.ok:
                tool_stat["ok"] += 1
            else:
                tool_stat["failed"] += 1
            tool_stat["total_ms"] += record.duration_ms

            # JSONL 落盘
            try:
                with open(TOOL_AUDIT_LOG, "a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(record), ensure_ascii=False, default=str) + "\n")
            except OSError as e:
                logger.warning("写入 tool_audit 日志失败 %s: %s", TOOL_AUDIT_LOG, e)

    def get_summary(self) -> dict:
        """返回聚合统计的快照。"""
        with self._file_lock:
            return {
                "total_calls": self._summary.total_calls,
                "ok_calls": self._summary.ok_calls,
                "failed_calls": self._summary.failed_calls,
                "total_duration_ms": self._summary.total_duration_ms,
                "by_tool": {k: dict(v) for k, v in self._summary.by_tool.items()},
                "log_file": str(TOOL_AUDIT_LOG),
            }


def get_tool_audit_recorder() -> ToolAuditRecorder:
    """获取全局工具审计记录器(单例)。"""
    return ToolAuditRecorder()
