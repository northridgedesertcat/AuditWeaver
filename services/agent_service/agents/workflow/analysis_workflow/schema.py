"""结构化输出 Schema(对齐 §3.1)。

字段均设默认值:本地小模型(如 qwen2.5:7b)tool calling 不稳,
漏字段时降级而非校验崩溃,与下游 build_report_record 默认值处理一致。

Schemas:
- AnalysisSchema: analyze 节点输出(沿用 v1)
- ValidateSchema: validate 节点输出(质量门控 PASS/FAIL + missing + reason)
- ReportSchema: report 节点输出(最终报告,带 source_id 引用)
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


class ValidateSchema(BaseModel):
    """validate 节点结构化输出:质量门控结果。

    用 light 模型省钱;检查 analysis 结论是否在 evidence_pack 中有 source 支撑、
    置信度是否达标。输出 PASS/FAIL + 缺失证据列表 + 原因。

    Attributes:
        pass_: 是否通过门控(pass=True → 走 report,pass=False → 走 enrich)
        missing: 缺失的证据项列表(攻击类型/IP/载荷等关键词),
            供 enrich 决定补检索词
        reason: 判断理由(可解释、可追溯)
    """
    # Pydantic v2 中 `pass` 是 Python 关键字,用 pass_ + alias
    pass_: bool = Field(
        default=False,
        alias="pass",
        description="是否通过质量门控(True=走 report, False=走 enrich)",
    )
    missing: list[str] = Field(
        default_factory=list,
        description="缺失的证据项,供 enrich 决定补检索词",
    )
    reason: str = Field(
        default="",
        description="判断理由(结论是否有 evidence 支撑 / 置信度是否达标)",
    )

    model_config = {"populate_by_name": True}


class ReportSchema(BaseModel):
    """report 节点结构化输出:最终报告(带 citation 反幻觉)。

    Attributes:
        report: 最终报告正文,所有结论必须挂 source_id 引用;
            无 evidence 支撑的结论必须显式标记"推测"
        cited_source_ids: 引用到的 source_id 列表(供前端/审计追溯)
        unresolved: 未被引用支撑的"推测"结论列表(反幻觉透明)
    """
    report: str = Field(
        default="",
        description="最终报告正文,结论挂 source_id,无引用标记推测",
    )
    cited_source_ids: list[str] = Field(
        default_factory=list,
        description="引用到的 source_id 列表",
    )
    unresolved: list[str] = Field(
        default_factory=list,
        description="无 evidence 支撑的推测结论列表(反幻觉透明)",
    )
