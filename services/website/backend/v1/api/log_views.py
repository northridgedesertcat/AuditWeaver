"""Authenticated log endpoints shared by legacy and hybrid storage modes."""
from datetime import datetime, timedelta, timezone

from rest_framework.response import Response
from rest_framework.views import APIView

from common.log_query import QueryError, QuerySpec, QueryUnavailable, get_log_query_service
from common.log_query.types import utcnow
from reports.models import AnalysisReport


def error_response(exc):
    return Response({"error": str(exc), "coverage": {"complete": False}},
                    status=400 if isinstance(exc, (QueryError, ValueError)) else 503)


class LogsView(APIView):
    def get(self, request):
        try:
            service = get_log_query_service()
            spec = service.spec_from_params(request.query_params)
            size, page = int(request.query_params.get("size", 20)), int(request.query_params.get("page", 1))
            if page < 1 or page > 10 or (page > 1 and request.query_params.get("cursor")):
                raise QueryError("Use cursor pagination after page 10; cursor and page cannot be combined")
            cursor = request.query_params.get("cursor")
            result = None
            for step in range(page):
                result = service.search(spec, limit=size, cursor=cursor)
                if not result["has_more"] and step < page - 1:
                    result["data"] = []
                    break
                cursor = result["next_cursor"]
            return Response({**result, "page": page, "size": size})
        except (QueryError, QueryUnavailable, ValueError) as exc:
            return error_response(exc)


class LogStatsView(APIView):
    def get(self, request):
        try:
            service = get_log_query_service()
            spec = service.spec_from_params(request.query_params)
            aggregate = service.aggregate(spec, dimensions=("ip", "path", "status"))
            today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_count = service.aggregate(QuerySpec("raw", today, utcnow()))["total"]
            return Response({
                "total": aggregate["total"], "today": today_count,
                "top_ips": [{"ip": key, "count": n} for key, n in aggregate["groups"]["ip"][:10]],
                "top_paths": [{"path": key, "count": n} for key, n in aggregate["groups"]["path"][:10]],
                "status_distribution": {str(key): n for key, n in aggregate["groups"]["status"]},
                "coverage": aggregate["coverage"],
            })
        except (QueryError, QueryUnavailable, ValueError) as exc:
            return error_response(exc)


class DashboardStatsView(APIView):
    def get(self, request):
        now = utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        reports = AnalysisReport.objects.filter(analysis_timestamp__gte=today)
        stats = {"logVolume": None, "totalLogs": None, "attackLogs": reports.count(),
                 "highSeverityAlerts": reports.filter(risk_level__in=["critical", "high"]).count(),
                 "riskIps": 0, "avgResponseTime": "0ms"}
        try:
            service = get_log_query_service()
            count = service.aggregate(QuerySpec("raw", today, now))["total"]
            total = service.aggregate(QuerySpec("raw", datetime(1970, 1, 1, tzinfo=timezone.utc), now))
            stats.update(logVolume=f"{count / 1000000:.1f}M" if count >= 1000000 else f"{count // 1000}K" if count >= 1000 else str(count),
                         totalLogs=total["total"], coverage=total["coverage"])
        except (QueryError, QueryUnavailable) as exc:
            stats.update(error=str(exc), coverage={"complete": False})
            return Response(stats, status=503)
        return Response(stats)


class LogTrendView(APIView):
    def get(self, request):
        try:
            service = get_log_query_service()
            spec = service.spec_from_params(request.query_params)
            if spec.end - spec.start > timedelta(days=90):
                raise QueryError("Trend range is limited to 90 days")
            result = service.aggregate(spec, hourly=True)
            counts = dict(result["hours"])
            cursor = spec.start.replace(minute=0, second=0, microsecond=0)
            data = []
            while cursor < spec.end:
                key = int(cursor.timestamp() * 1000)
                data.append({"time": key, "logs": counts.get(key, 0)})
                cursor += timedelta(hours=1)
            return Response({"data": data, "coverage": result["coverage"]})
        except (QueryError, QueryUnavailable, ValueError) as exc:
            return error_response(exc)
