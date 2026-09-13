"""Skill 2: QueryAnalysisResults —— 查询日志分析 Agent 产出的分析报告。

数据源:MySQL ``analysis_report`` 表(原 ES log_analysis_reports 索引已迁移)。
仅读,参数化 SQL,时间过滤沿用 common.time_utils.parse_time_range。
"""
from common.time_utils import (
    parse_time_range,
    to_epoch_millis,
    utc_from_epoch_millis,
)
from .db import query
from .config.settings import MAX_SIZE_REPORTS


def query_analysis_results(
    ip: str | None = None,
    risk_level: str = "all",
    time_range: str = "24h",
    size: int = 20,
) -> dict:
    """查询日志分析报告(按 IP / 风险等级 / 时间范围过滤)。

    Args:
        ip: 目标 IP;不传则查所有 IP。
        risk_level: 风险等级,可选 Critical / High / Medium / Low / Normal / all,默认 all
            (大小写不敏感,库内统一小写存储)。
        time_range: 时间范围,可选 15m / 1h / 24h / 7d / all,默认 24h。
        size: 返回条数上限(最大 100),默认 20。

    Returns:
        dict: {ip, risk_level, time_range, total, returned, reports: [...]}
    """
    size = max(1, min(int(size or 20), MAX_SIZE_REPORTS))
    gte_ms, lte_ms = parse_time_range(time_range)

    # WHERE 条件与参数顺序严格对齐
    where = ["analysis_timestamp <= %s"]
    params: list = [utc_from_epoch_millis(lte_ms)]
    if gte_ms > 0:
        where = ["analysis_timestamp BETWEEN %s AND %s"]
        params = [utc_from_epoch_millis(gte_ms), utc_from_epoch_millis(lte_ms)]
    if ip:
        where.append("ip = %s")
        params.append(ip)
    if risk_level and risk_level.lower() != "all":
        where.append("risk_level = %s")
        params.append(risk_level.lower())

    where_sql = " AND ".join(where)

    count_rows = query(
        f"SELECT COUNT(*) AS c FROM analysis_report WHERE {where_sql}",
        tuple(params),
    )
    if count_rows is None:
        return {
            "ip": ip,
            "risk_level": risk_level,
            "time_range": time_range,
            "total": 0,
            "returned": 0,
            "reports": [],
            "error": "mysql unavailable",
        }
    total = int(count_rows[0]["c"])

    rows = query(
        "SELECT event_id, ip, attack_type_ai, risk_level, risk_score, summary, "
        f"analysis_timestamp FROM analysis_report WHERE {where_sql} "
        "ORDER BY analysis_timestamp DESC LIMIT %s",
        tuple(params + [size]),
    )

    reports = []
    for r in rows or []:
        # VARBINARY 列在 DictCursor 下可能返回 bytes
        row_ip = r.get("ip")
        if isinstance(row_ip, (bytes, bytearray)):
            row_ip = row_ip.decode("utf-8", errors="replace")
        reports.append({
            "event_id": r.get("event_id"),
            "ip": row_ip,
            "attack_type_ai": r.get("attack_type_ai"),
            "risk_level": r.get("risk_level"),
            "risk_score": r.get("risk_score"),
            "summary": r.get("summary"),
            "analysis_timestamp": to_epoch_millis(r.get("analysis_timestamp")),
        })

    return {
        "ip": ip,
        "risk_level": risk_level,
        "time_range": time_range,
        "total": total,
        "returned": len(reports),
        "reports": reports,
    }
