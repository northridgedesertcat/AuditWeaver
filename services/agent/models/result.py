# 处理结果模型
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime


@dataclass
class ProcessResult:
    """处理结果模型"""
    
    task_id: str
    event_id: str
    success: bool
    dify_response: Dict
    processed_at: str = ""
    
    def __post_init__(self):
        if not self.processed_at:
            self.processed_at = datetime.now().isoformat()
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ProcessResult":
        """从字典创建结果"""
        return cls(
            task_id=data.get("task_id", ""),
            event_id=data.get("event_id", ""),
            success=data.get("success", False),
            dify_response=data.get("dify_response", {}),
            processed_at=data.get("processed_at", datetime.now().isoformat())
        )
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "event_id": self.event_id,
            "success": self.success,
            "dify_response": self.dify_response,
            "processed_at": self.processed_at
        }
