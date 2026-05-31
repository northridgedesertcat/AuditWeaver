#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LogSentinel Agent 启动脚本
用于启动 agent 模块，保持模块内部使用相对导入
"""
import sys
import os

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 将 services 目录添加到 Python 路径
services_dir = current_dir
if services_dir not in sys.path:
    sys.path.insert(0, services_dir)

# 使用包导入方式启动 agent
from agent.main import main

if __name__ == "__main__":
    main()
