"""启动时按形态遍历 agent 子目录,触发各自注册。

agents 按形态分两类目录:
    react/    对话型 ReAct agent(多轮工具循环)
    workflow/ 线性批处理工作流(单次执行,结构化输入输出)

新增 Agent 时在对应形态目录中新建子包,并在此追加一行:
    from .react import rule_advisor    # noqa: F401
    from .workflow import log_cleaner  # noqa: F401
"""
from . import react     # noqa: F401  # 触发 react/__init__.py 内各 agent 注册
from . import workflow  # noqa: F401  # 触发 workflow/__init__.py 内各 workflow 注册
