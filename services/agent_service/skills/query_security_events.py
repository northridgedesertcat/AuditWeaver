"""Skill 3: QuerySecurityEvents —— 查询规则匹配命中的安全事件。

数据源:统一冷热事件查询。
"""
from common.time_utils import to_epoch_millis
from .log_search import search_logs
from common.log_query import QueryError, QueryUnavailable
from .config.settings import MAX_SIZE_EVENTS


def _extract_detection(source: dict) -> tuple[str | None, str | None]:
    """从 matched_logs 的 detections 嵌套结构中取首个 rule_id 与 matched_value。"""
    det = source.get("detections") or []
    if not det or not isinstance(det, list):
        return None, None
    first = det[0] or {}
    rule_id = first.get("rule_id")
    matches = first.get("matches") or []
    matched_value = None
    if matches and isinstance(matches, list):
        matched_value = (matches[0] or {}).get("matched_value")
    return rule_id, matched_value


def query_security_events(
    attack_type: str = "all",
    ip: str | None = None,
    time_range: str = "24h",
    size: int = 50,
) -> dict:
    """查询安全事件(按攻击类型 / IP / 时间范围过滤)。

    Args:
        attack_type: 攻击类型,如 sql_injection / xss / path_traversal / command_injection / sensitive_access;all 表示不过滤,默认 all。
        ip: 目标 IP;不传则查所有 IP。
        time_range: 时间范围,可选 15m / 1h / 24h / 7d / 30d / 90d,默认 24h。
        size: 返回条数上限(最大 200),默认 50。

    Returns:
        dict: {attack_type, ip, time_range, total, returned, events: [...]}
    """
    size = max(1, min(int(size or 50), MAX_SIZE_EVENTS))

    try:
        filters = {"ip": ip}
        if attack_type and attack_type.lower() != "all":
            filters["attack_type"] = attack_type
        resp = search_logs("events", time_range, size, filters)
    except (QueryError, QueryUnavailable) as exc:
        return {"attack_type": attack_type, "ip": ip, "time_range": time_range, "total": None, "returned": 0,
                "events": [], "coverage": {"complete": False}, "error": str(exc)}
    if resp is None:
        return {
            "attack_type": attack_type,
            "ip": ip,
            "time_range": time_range,
            "total": None,
            "returned": 0,
            "events": [],
            "error": "log storage unavailable",
            "coverage": {"complete": False},
        }

    hits = (resp.get("hits") or {})
    total = hits.get("total")
    if isinstance(total, dict):
        total = total.get("value", 0)
    if not isinstance(total, int):
        total = int(total or 0)

    events = []
    for h in hits.get("hits", []):
        s = h.get("_source", {}) or {}
        ctx = s.get("log_context") or {}
        rule_id, matched_value = _extract_detection(s)
        events.append({
            "event_id": s.get("event_id"),
            "attack_type": s.get("attack_type"),
            "ip": ctx.get("ip"),
            "path": ctx.get("path"),
            "method": ctx.get("method"),
            "status": ctx.get("status"),
            "matched_value": matched_value,
            "rule_id": rule_id,
            "timestamp": to_epoch_millis(ctx.get("timestamp")),
        })

    return {
        "attack_type": attack_type,
        "ip": ip,
        "time_range": time_range,
        "total": total,
        "returned": len(events),
        "events": events,
        "coverage": resp.get("coverage"),
        "has_more": resp.get("has_more", False),
    }
