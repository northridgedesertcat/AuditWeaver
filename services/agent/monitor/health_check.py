# 健康检查模块
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self.checks = []
    
    def register_check(self, name: str, check_func):
        """注册健康检查"""
        self.checks.append({"name": name, "check": check_func})
    
    def check_all(self) -> Dict[str, bool]:
        """运行所有健康检查"""
        results = {}
        for check in self.checks:
            try:
                results[check["name"]] = check["check"]()
            except Exception as e:
                logger.error(f"健康检查 {check['name']} 失败: {str(e)}")
                results[check["name"]] = False
        return results
    
    def is_healthy(self) -> bool:
        """检查整体健康状态"""
        results = self.check_all()
        return all(results.values())
    
    def report(self) -> str:
        """生成健康报告"""
        results = self.check_all()
        status = "HEALTHY" if self.is_healthy() else "UNHEALTHY"
        report = f"健康状态: {status}\n"
        report += "---\n"
        for name, healthy in results.items():
            report += f"{name}: {'✓' if healthy else '✗'}\n"
        return report
