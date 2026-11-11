"""Skill 1: QueryIPLogs —— 查询某 IP 的原始 nginx 访问日志。

数据源:统一冷热日志查询。
"""
from common.time_utils import to_epoch_millis
from .log_search import search_logs
from common.log_query import QueryError, QueryUnavailable
from .config.settings import MAX_SIZE_RAW


def query_ip_logs(ip: str, time_range: str = "24h", size: int = 50) -> dict:
    """查询目标 IP 在最近时间范围内的原始访问日志。

    Args:
        ip: 目标 IP 地址(必填)。
        time_range: 时间范围,可选 15m / 1h / 24h / 7d / 30d / 90d,默认 24h。
        size: 返回条数上限(最大 200),默认 50。

    Returns:
        dict: {ip, total, returned, time_range, logs: [...]}
    """
    size = max(1, min(int(size or 50), MAX_SIZE_RAW))

    try:
        resp = search_logs("raw", time_range, size, {"ip": ip})
    except (QueryError, QueryUnavailable) as exc:
        return {"ip": ip, "total": None, "returned": 0, "time_range": time_range, "logs": [],
                "coverage": {"complete": False}, "error": str(exc)}
    if resp is None:
        return {
            "ip": ip,
            "total": None,
            "returned": 0,
            "time_range": time_range,
            "logs": [],
            "error": "log storage unavailable",
            "coverage": {"complete": False},
        }

    hits = (resp.get("hits") or {})
    total = hits.get("total")
    if isinstance(total, dict):
        total = total.get("value", 0)
    if not isinstance(total, int):
        total = int(total or 0)

    logs = []
    for h in hits.get("hits", []):
        s = h.get("_source", {}) or {}
        logs.append({
            "timestamp": to_epoch_millis(s.get("@timestamp")),
            "method": s.get("method"),
            "path": s.get("path"),
            "status": s.get("status"),
            "user_agent": s.get("user_agent"),
            "event_id": s.get("event_id"),
        })

    return {
        "ip": ip,
        "total": total,
        "returned": len(logs),
        "time_range": time_range,
        "logs": logs,
        "coverage": resp.get("coverage"),
        "has_more": resp.get("has_more", False),
    }
