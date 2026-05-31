# 状态枚举
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    
    def __str__(self):
        return self.value


class RuleMatchingStatus(str, Enum):
    """规则匹配状态枚举"""
    
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    
    def __str__(self):
        return self.value
