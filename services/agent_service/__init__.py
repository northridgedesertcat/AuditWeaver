"""AuditWeaver Agent Service —— 承载所有 Agent 的统一服务。

第一版只实现 Analysis Explorer Agent(对话式安全分析),但目录结构、
路由、共享层都按"未来会有 N 个 Agent"设计。新增 Agent 只需:
  1. 在 ``agents/`` 下新增一个子包(写 graph / prompts / nodes)。
  2. 在该子包 ``__init__.py`` 中调用 ``registry.register_agent``。
  3. 路由 ``/agent/{agent_type}/chat`` 自动可用,无需改 FastAPI / Django 代码。
"""
