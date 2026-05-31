# 任务模型
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime
import uuid


@dataclass
class Task:
    """任务模型"""
    
    task_id: str
    event_id: str
    data: Dict
    timestamp: str
    status: str = "pending"
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        """从字典创建任务"""
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            event_id=data.get("event_id", ""),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            status=data.get("status", "pending")
        )
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "event_id": self.event_id,
            "data": self.data,
            "timestamp": self.timestamp,
            "status": self.status
        }
    
    @classmethod
    def create_from_log(cls, log_entry: Dict) -> "Task":
        """从日志条目创建任务"""
        return cls(
            task_id=str(uuid.uuid4()),
            event_id=log_entry.get("event_id", str(uuid.uuid4())),
            data=log_entry,
            timestamp=datetime.now().isoformat()
        )
