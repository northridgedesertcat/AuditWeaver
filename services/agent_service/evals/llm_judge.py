"""LLM Judge:用 light 模型对 Agent 的 final_report 打主观质量分(对齐 §3.8 ③)。

设计要点:
- 用 role='light' 模型省钱(质量判断不需强推理,对齐 decision_llm/validate 思路)
- 输出结构化 {score: 1-5, reason: str}(JudgeSchema)
- 评分 rubric:1=答非所问/2=方向错/3=部分对/4=基本对/5=准确且有引用
- 不虚构分数:本模块只提供打分能力,真实分数由 run_eval --judge 跑出

面试能讲什么:LLM-as-Judge 的可靠性局限(同模型自评偏差)、rubric 设计、
主观质量如何客观化(多 judge 投票/对比 baseline)。
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from shared.llm.factory import get_llm
from shared.llm.retry import invoke_structured_with_retry

logger = logging.getLogger(__name__)

# rubric 提示(对齐 §3.8 主观质量维度)
_JUDGE_SYSTEM = """你是安全分析报告的质量评审员。按以下 rubric 对报告打分(1-5 整数):

- 5: 结论准确,引用了 source_id 证据,调查路径合理
- 4: 结论基本正确,但证据引用或调查路径有小瑕疵
- 3: 部分正确,遗漏关键点或证据不足
- 2: 方向错误或结论与输入无关
- 1: 答非所问或无有效内容

严格按 rubric 打分,给出理由(<=80 字)。只输出 JSON。"""


class JudgeSchema(BaseModel):
    """LLM Judge 结构化输出(对齐 §3.8 主观质量)。"""
    score: int = Field(..., description="1-5 整数分数")
    reason: str = Field("", description="打分理由(<=80 字)")


def _render_judge_prompt(user_input: str, report: str, rubric: str) -> list:
    """构造 judge prompt(system + user)。

    user_input: 原始用户问题;report: Agent 的 final_report;rubric: 该 case 的评分指引。
    """
    user_text = (
        f"用户问题:\n{user_input}\n\n"
        f"评审 rubric:\n{rubric or '(无特定 rubric,按通用标准)'}\n\n"
        f"Agent 报告:\n{report}\n\n"
        f"请按 rubric 打分。"
    )
    return [
        SystemMessage(content=_JUDGE_SYSTEM),
        HumanMessage(content=user_text),
    ]


async def judge_report(
    user_input: str, report: str, rubric: str = "",
) -> dict[str, Any]:
    """对单个 final_report 打分,返回 {score, reason}。

    用 light 模型 + JudgeSchema 结构化输出 + retry(对齐项目 LLM 调用契约)。
    失败时返回 {score: None, error: ...}(不抛,让 run_eval 继续跑其他 case)。
    """
    try:
        llm = get_llm(role="light", temperature=0.0, streaming=False)
        # function_calling:DeepSeek 不支持 response_format json_schema(实测 400)
        llm_structured = llm.with_structured_output(JudgeSchema, method="function_calling")
        messages = _render_judge_prompt(user_input, report, rubric)
        result = await invoke_structured_with_retry(
            llm_structured, messages, JudgeSchema, role="light",
        )
        d = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        return {"score": d.get("score"), "reason": d.get("reason", "")}
    except Exception as e:
        logger.warning("[llm_judge] 打分失败: %s: %s", type(e).__name__, e)
        return {"score": None, "error": f"{type(e).__name__}: {e}"}
