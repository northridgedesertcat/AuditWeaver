from datetime import timedelta

from common.log_query import QueryError, QuerySpec, QueryUnavailable, get_log_query_service
from common.log_query.types import utcnow


def search_logs(kind, time_range, size, filters):
    now = utcnow()
    durations = {"15m": timedelta(minutes=15), "1h": timedelta(hours=1), "24h": timedelta(days=1),
                 "7d": timedelta(days=7), "30d": timedelta(days=30), "90d": timedelta(days=90)}
    if time_range == "all":
        raise QueryError("Choose an explicit range up to 90d; all history exceeds the interactive query budget")
    if time_range not in durations:
        raise QueryError("Invalid time_range")
    service = get_log_query_service()
    spec = QuerySpec(kind, now - durations[time_range], now, filters)
    page = service.search(spec, limit=size)
    total = service.aggregate(spec)["total"]
    return {"hits": {"total": {"value": total}, "hits": [{"_source": row} for row in page["data"]]},
            "coverage": page["coverage"], "has_more": page["has_more"]}
