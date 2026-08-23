"""启动时遍历所有 agent 子包,触发各自注册。

新增 Agent 时在此追加一行,例如:
    from . import rule_advisor  # noqa: F401
"""
from . import analysis_explorer  # noqa: F401
