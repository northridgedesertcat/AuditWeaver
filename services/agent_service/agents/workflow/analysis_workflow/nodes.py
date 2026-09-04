"""analyze_node:构建 prompt → LLM 结构化输出。

ollama 本地模型不支持 function calling,用 with_structured_output(method='json_schema')
走 OpenAI structured outputs 格式(ollama 0.24+ 支持),由 ollama grammar 强约束输出。

v2 预留 retrieve_node 的接入位置(仅改 graph.py,不改此文件)。
"""
import asyncio

from shared.llm.factory import get_llm
from .config.settings import TEMPERATURE, LLM_MODEL, LLM_BASE_URL, LLM_API_KEY
from .prompts import render_prompt
from .schema import AnalysisSchema

# 进程内缓存:structured LLM 只初始化一次,所有调用复用
_llm_structured = None
_init_lock = asyncio.Lock()


async def _ensure() -> None:
    """懒加载 LLM + with_structured_output,只初始化一次。"""
    global _llm_structured
    if _llm_structured is not None:
        return
    async with _init_lock:
        if _llm_structured is not None:
            return
        llm = get_llm(temperature=TEMPERATURE, model=LLM_MODEL,
                      base_url=LLM_BASE_URL, api_key=LLM_API_KEY,
                      streaming=False)  # json_schema response_format 不支持 streaming
        # method='json_schema':ollama 0.24+ / OpenAI 官方均支持,
        # 用 response_format=json_schema 在推理层强约束输出格式
        _llm_structured = llm.with_structured_output(AnalysisSchema, method="json_schema")


async def analyze_node(state: dict) -> dict:
    """LLM 分析节点:基于日志 + 检索上下文(v1 为空),产出结构化分析。"""
    await _ensure()
    messages = render_prompt(
        state.get("log_data", {}),
        state.get("retrieved_context", ""),
    )
    result = await _llm_structured.ainvoke(messages)
    # Pydantic v2: model_dump(); 兼容 v1 回退
    if hasattr(result, "model_dump"):
        return {"analysis": result.model_dump()}
    return {"analysis": dict(result)}


# ============ v2 预留(本阶段不实现)============
# import json
#
# async def retrieve_node(state: dict) -> dict:
#     """知识库向量检索节点(v2)。
#     对齐 Dify Knowledge Retrieval:embedding → kNN → top_k=4。
#     """
#     log_data = state.get("log_data", {})
#     query = json.dumps(log_data, ensure_ascii=False)
#     # v2: embed query → ES kNN search → 拼接 context
#     return {"retrieved_context": retrieved_text}
