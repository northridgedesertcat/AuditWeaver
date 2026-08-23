"""MCP Server 入口:挂载三个只读 Skill 工具。

由 Agent Service 进程通过 stdio 子进程拉起:
    python -m services.agent_service.skills.server

任何 Agent 都能调用同一套 Skills,Skills 不绑定具体 Agent。
"""
from mcp.server.fastmcp import FastMCP

from .query_ip_logs import query_ip_logs
from .query_analysis_results import query_analysis_results
from .query_security_events import query_security_events

mcp = FastMCP("agent-service-skills")

mcp.tool()(query_ip_logs)
mcp.tool()(query_analysis_results)
mcp.tool()(query_security_events)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
