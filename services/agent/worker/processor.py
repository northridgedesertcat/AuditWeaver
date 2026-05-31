# 任务处理器 - 负责单条任务的处理逻辑
from typing import Dict
import logging
import sys
import os

current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)
agent_dir = os.path.dirname(current_dir)
if agent_dir not in sys.path:
    sys.path.insert(0, agent_dir)

from dify import DifyClient
from es_client import DataWriter
from models import Task
from constants import TASK_STATUS

logger = logging.getLogger(__name__)


class TaskProcessor:
    """任务处理器 - 处理单条任务"""

    def __init__(self, dify_client: DifyClient, data_writer: DataWriter):
        self.dify_client = dify_client
        self.data_writer = data_writer

    def process(self, task_data: Dict) -> bool:
        """处理单个任务"""
        try:
            task_obj = Task.from_dict(task_data)
            logger.info(f"[{task_obj.event_id}] 开始处理任务")

            dify_result = self.dify_client.process(task_obj.data)

            # 写入到 agent_analysis_logs 索引
            success = self.data_writer.write_processed_log(
                task_obj.data,
                dify_result,
                task_obj.event_id
            )

            if success:
                logger.info(f"[{task_obj.event_id}] 任务处理完成，已写入 agent_analysis_logs")
                return True
            else:
                logger.warning(f"[{task_obj.event_id}] 任务处理失败")
                return False
        except Exception as e:
            logger.error(f"处理任务失败：{str(e)}", exc_info=True)
            return False
