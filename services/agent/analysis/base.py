"""分析后端协议与归一化结果。

两个实现(DifyAnalysisBackend / LangGraphAnalysisBackend)都满足此协议,
下游 main.py 与 build_report_record 只依赖 AnalysisResult,不感知后端类型。
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class AnalysisResult:
    """归一化分析结果,字段对齐 extract_dify_fields 输出与 analysis_report 列。"""

    status: str               # 'success' | 'failed' | 'degraded'(熔断打开期降级,AI 字段全空,仅保留规则匹配)
    log_id: str
    risk_level: str = 'unknown'
    risk_score: int = 0
    attack_type_ai: str = ''  # 对应 Dify 输出 attack_type，落库列名 attack_type_ai
    summary: str = ''
    reasoning: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    raw_response: dict = field(default_factory=dict)  # 落库到 analysis_report.raw_response（LLM 原始响应存档）
    error: str | None = None


class AnalysisBackend(Protocol):
    """分析后端协议:输入原始 Kafka 消息,返回归一化结果。"""

    def analyze(self, raw_message: dict) -> AnalysisResult:
        ...

    def close(self) -> None:
        ...
