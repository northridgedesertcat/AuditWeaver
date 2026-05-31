﻿# 任务处理器 - 保留以兼容旧代码，新代码使用 processor.py
# 本文件会在未来版本中移除
import sys
import os

current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)
agent_dir = os.path.dirname(current_dir)
if agent_dir not in sys.path:
    sys.path.insert(0, agent_dir)

from worker.processor import TaskProcessor

__all__ = ["TaskProcessor"]
