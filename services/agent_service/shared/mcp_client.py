"""MCP Client:连接 Skills(stdio),把工具转成 LangChain Tool 列表。

- 连接方式:stdio。Agent Service 进程拉起子进程
  ``python -m services.agent_service.skills.server``。
- 工具列表缓存:所有 Agent 共用同一个 MCP 连接(单例)。
- 同机部署,无需额外端口。

注意:子进程继承父进程 cwd,因此 uvicorn 必须从项目根目录启动
(start.py 已保证),子进程才能 ``import common`` 与解析 ``services`` 包。
"""
import asyncio
import sys

from langchain_core.tools import BaseTool

_PROJECT_ROOT_HINT = "uvicorn 须从项目根目录启动,否则 Skills 子进程无法 import common"


class _MCPHolder:
    """单例 holder,懒加载,避免 import 时建连。"""

    def __init__(self) -> None:
        self.client = None
        self.tools: list[BaseTool] | None = None
        self.lock = asyncio.Lock()

    async def load(self) -> list[BaseTool]:
        if self.tools is not None:
            return self.tools
        async with self.lock:
            if self.tools is not None:
                return self.tools
            from langchain_mcp_adapters.client import MultiServerMCPClient

            self.client = MultiServerMCPClient(
                {
                    "agent-skills": {
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": ["-m", "services.agent_service.skills.server"],
                    }
                }
            )
            self.tools = await self.client.get_tools()
            if self.tools is None:
                self.tools = []
            return self.tools


_holder = _MCPHolder()


async def get_mcp_tools() -> list[BaseTool]:
    """返回共享的 MCP 工具列表(LangChain BaseTool)。"""
    return await _holder.load()
