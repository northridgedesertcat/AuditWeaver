"""Skill 2: QueryAnalysisResults —— 查询日志分析 Agent 产出的分析报告。

数据源:``log_analysis_reports``。
"""
from common.time_utils import parse_time_range, to_epoch_millis
from .es import search
from .config.settings import ES_INDEX_REPORTS, MAX_SIZE_REPORTS


def query_analysis_results(
    ip: str | None = None,
    risk_level: str = "all",
    time_range: str = "24h",
    size: int = 20,
) -> dict:
    """查询日志分析报告(按 IP / 风险等级 / 时间范围过滤)。

    Args:
        ip: 目标 IP;不传则查所有 IP。
        risk_level: 风险等级,可选 Critical / High / Medium / Low / Normal / all,默认 all。
        time_range: 时间范围,可选 15m / 1h / 24h / 7d / all,默认 24h。
        size: 返回条数上限(最大 100),默认 20。

    Returns:
        dict: {ip, risk_level, time_range, total, returned, reports: [...]}
    """
    size = max(1, min(int(size or 20), MAX_SIZE_REPORTS))
    gte, lte = parse_time_range(time_range)

    must = [{"range": {"analysis_timestamp": {"gte": gte, "lte": lte}}}]
    if ip:
        must.append({"term": {"ip": ip}})
    if risk_level and risk_level.lower() != "all":
        must.append({"terms": {"risk_level": [risk_level]}})

    body = {
        "size": size,
        "query": {"bool": {"must": must}},
        "sort": [{"analysis_timestamp": {"order": "desc"}}],
    }

    resp = search(ES_INDEX_REPORTS, body)
    if resp is None:
        return {
            "ip": ip,
            "risk_level": risk_level,
            "time_range": time_range,
            "total": 0,
            "returned": 0,
            "reports": [],
            "error": "elasticsearch unavailable",
        }

    hits = (resp.get("hits") or {})
    total = hits.get("total")
    if isinstance(total, dict):
        total = total.get("value", 0)
    if not isinstance(total, int):
        total = int(total or 0)

    reports = []
    for h in hits.get("hits", []):
        s = h.get("_source", {}) or {}
        reports.append({
            "event_id": s.get("event_id"),
            "ip": s.get("ip"),
            "attack_type_ai": s.get("attack_type_ai"),
            "risk_level": s.get("risk_level"),
            "risk_score": s.get("risk_score"),
            "summary": s.get("summary"),
            "analysis_timestamp": to_epoch_millis(s.get("analysis_timestamp")),
        })

    return {
        "ip": ip,
        "risk_level": risk_level,
        "time_range": time_range,
        "total": total,
        "returned": len(reports),
        "reports": reports,
    }
