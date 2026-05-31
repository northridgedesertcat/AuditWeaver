# 消息队列模块初始化
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
agent_dir = os.path.dirname(current_dir)
if agent_dir not in sys.path:
    sys.path.insert(0, agent_dir)

from .consumer import KafkaConsumerClient
from .producer import KafkaProducer

__all__ = ["KafkaConsumerClient", "KafkaProducer"]
