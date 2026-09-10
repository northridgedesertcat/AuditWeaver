"""结构化输出 Schema,字段与 Dify 逐字一致。

字段均设默认值:本地小模型(如 qwen2.5:7b)tool calling 不稳,
漏字段时降级而非校验崩溃,与下游 build_report_record 默认值处理一致。
"""
from pydantic import BaseModel, Field


class AnalysisSchema(BaseModel):
    """LLM 结构化输出模型,对齐 Dify structured_output schema。"""

    risk_level: str = Field(default="unknown", description="风险等级:Critical / High / Medium / Low / Normal")
    risk_score: int = Field(default=0, description="风险评分:0-100")
    attack_type: str = Field(default="", description="攻击类型")
    summary: str = Field(default="", description="分析摘要")
    reasoning: list[str] = Field(default_factory=list, description="推理过程")
    recommendations: list[str] = Field(default_factory=list, description="修复建议")
