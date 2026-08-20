"""Analysis Explorer Agent 的节点:agent_node(LLM 决策)+ tools_node(执行 MCP 工具)。

工具通过 MCP Client 取得,所有 Agent 共用;LLM 通过 ``bind_tools`` 决定调几个。
"""
import asyncio

from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode

from shared.llm.factory import get_llm
from shared.mcp_client import get_mcp_tools
from .prompts import SYSTEM_PROMPT

# 进程内缓存:LLM 与 tools 只初始化一次,所有调用复用
_llm = None
_llm_with_tools = None
_tools_node = None
_init_lock = asyncio.Lock()


async def _ensure() -> None:
    """懒加载 LLM + MCP 工具,只初始化一次。"""
    global _llm, _llm_with_tools, _tools_node
    if _llm_with_tools is not None:
        return
    async with _init_lock:
        if _llm_with_tools is not None:
            return
        _llm = get_llm()
        tools = await get_mcp_tools()
        if tools:
            _llm_with_tools = _llm.bind_tools(tools)
            _tools_node = ToolNode(tools)
        else:
            # 没有可用工具时退化为直接对话
            _llm_with_tools = _llm
            _tools_node = None


async def agent_node(state: dict) -> dict:
    """LLM 决策节点:直接回答 or 发起 tool_calls。"""
    await _ensure()
    # 每轮都把系统提示词置于历史之前,LLM 始终看到角色约束 + 完整历史
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
    response = await _llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


async def tools_node(state: dict) -> dict:
    """工具执行节点:实际工具是 MCP Client 包装的 LangChain Tool。"""
    await _ensure()
    if _tools_node is None:
        return {"messages": []}
    return await _tools_node.ainvoke(state)
