"""Skill 3: QuerySecurityEvents —— 查询规则匹配命中的安全事件。

数据源:``matched_logs``。
"""
from common.time_utils import parse_time_range, to_epoch_millis
from .es import search
from .config.settings import ES_INDEX_EVENTS, MAX_SIZE_EVENTS


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
        time_range: 时间范围,可选 15m / 1h / 24h / 7d / all,默认 24h。
        size: 返回条数上限(最大 200),默认 50。

    Returns:
        dict: {attack_type, ip, time_range, total, returned, events: [...]}
    """
    size = max(1, min(int(size or 50), MAX_SIZE_EVENTS))
    gte, lte = parse_time_range(time_range)

    must = [{"range": {"log_context.timestamp": {"gte": gte, "lte": lte}}}]
    if attack_type and attack_type.lower() != "all":
        must.append({"term": {"attack_type": attack_type}})
    if ip:
        must.append({"term": {"log_context.ip": ip}})

    body = {
        "size": size,
        "query": {"bool": {"must": must}},
        "sort": [{"log_context.timestamp": {"order": "desc"}}],
    }

    resp = search(ES_INDEX_EVENTS, body)
    if resp is None:
        return {
            "attack_type": attack_type,
            "ip": ip,
            "time_range": time_range,
            "total": 0,
            "returned": 0,
            "events": [],
            "error": "elasticsearch unavailable",
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
    }
