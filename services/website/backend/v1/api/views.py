from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, exceptions as drf_exceptions
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import (
    AlertSerializer,
    AlertRuleSerializer,
    IncidentSerializer,
    AnomalySerializer,
    ServerSerializer,
    ThreatSerializer,
    AIModelSerializer,
)
from .mock_data import (
    MOCK_ALERTS,
    MOCK_ALERT_RULES,
    MOCK_INCIDENTS,
    MOCK_ANOMALIES,
    MOCK_SERVERS,
    MOCK_THREATS,
    MOCK_AI_MODELS,
    MOCK_RECENT_ANALYSES,
    MOCK_THREAT_FEEDS,
    ALERT_STATS,
    INCIDENT_STATS,
    ANOMALY_STATS,
    INFRA_STATS,
    THREAT_STATS,
    AI_STATS,
)
from .es_client import is_es_available
import sys
import os
# 添加 services 目录到路径，以便导入 common 模块
_services_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
if _services_path not in sys.path:
    sys.path.insert(0, _services_path)

# Agent Service 反代所需(透传 SSE 流到内部 FastAPI :8001)
import httpx
from django.http import StreamingHttpResponse, JsonResponse
from django.conf import settings as django_settings
from rest_framework.renderers import BaseRenderer, JSONRenderer


class EventStreamRenderer(BaseRenderer):
    """占位 renderer:仅用于通过 DRF 内容协商。

    AgentProxyView 的响应均为手动构造的 StreamingHttpResponse / JsonResponse,
    实际不走 renderer 渲染;此处只让 DRF 接受前端 Accept: text/event-stream,
    否则 DRF 默认 renderer 不支持该媒体类型,会在进入视图前返回 406。
    """

    media_type = 'text/event-stream'
    format = 'event-stream'


class AgentProxyView(APIView):
    """Django → FastAPI 反代。透传请求体与 SSE 流,保留 agent_type 路径段。

    - POST  /api/v1/agent/<agent_type>/chat       → 流式透传 SSE
    - POST  /api/v1/agent/<agent_type>/chat/sync  → 透传 JSON
    - GET   /api/v1/agent/health | /agent/types    → 透传 JSON

    FastAPI 不可用时返回 502,不抛栈;未知 agent_type 由 FastAPI 返回 404 透传。
    """
    permission_classes = [IsAuthenticated]
    renderer_classes = [EventStreamRenderer, JSONRenderer]

    def handle_exception(self, exc):
        """错误响应统一走原生 JsonResponse,绕过 DRF 内容协商/渲染。

        前端请求带 Accept: text/event-stream,DRF 内容协商会选中占位用的
        EventStreamRenderer(仅为通过协商,未实现 render())。若认证失败(401)、
        限流(429)等 DRF 异常走默认 Response 渲染,render() 会抛
        NotImplementedError,把真实状态码全部吞成 500。JsonResponse 不是
        DRF Response,不会经过 renderer,状态码与 JSON body 都能正确返回。
        """
        if isinstance(exc, drf_exceptions.APIException):
            detail = exc.detail
            return JsonResponse(
                {"detail": str(detail) if not isinstance(detail, (list, dict)) else detail},
                status=exc.status_code,
            )
        return super().handle_exception(exc)

    def _build_target(self, request):
        # request.path_info 形如 /api/v1/agent/analysis_explorer/chat
        # 截掉 /api/v1 前缀,拼到 FastAPI base,完整保留 agent_type 与子路径
        prefix = "/api/v1"
        path_info = request.path_info or ""
        tail = path_info[len(prefix):] if path_info.startswith(prefix) else path_info
        return f"{django_settings.AGENT_FASTAPI_BASE}{tail}"

    def post(self, request, *args, **kwargs):
        target = self._build_target(request)
        body = request.body or b""
        headers = {"Content-Type": request.content_type or "application/json"}

        client = httpx.Client(timeout=None)
        try:
            req = httpx.Request("POST", target, content=body, headers=headers)
            upstream = client.send(req, stream=True)
        except httpx.HTTPError:
            client.close()
            # 用原生 JsonResponse 而非 DRF Response:后者会被 EventStreamRenderer
            # 渲染而抛 NotImplementedError,把 502 吞成 500(与 handle_exception 同理)
            return JsonResponse(
                {"error": "agent service unavailable"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        def stream():
            try:
                for chunk in upstream.iter_bytes():
                    yield chunk
            finally:
                upstream.close()
                client.close()

        # 透传上游 content-type:/chat 为 text/event-stream,/chat/sync 为 application/json
        content_type = upstream.headers.get("content-type", "text/event-stream")
        resp = StreamingHttpResponse(stream(), content_type=content_type, status=upstream.status_code)
        resp["X-Accel-Buffering"] = "no"   # 禁用 nginx 缓冲,保证 SSE 实时
        resp["Cache-Control"] = "no-cache"
        return resp

    def get(self, request, *args, **kwargs):
        target = self._build_target(request)
        try:
            r = httpx.get(target, timeout=10)
            return JsonResponse(r.json(), status=r.status_code, safe=False)
        except httpx.HTTPError:
            return JsonResponse(
                {"error": "agent service unavailable"},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        es_available = is_es_available()
        return Response({
            "status": "ok",
            "elasticsearch": "available" if es_available else "unavailable"
        })




class AlertsView(APIView):
    def get(self, request):
        severity = request.query_params.get('severity', 'all')
        status = request.query_params.get('status', 'all')
        
        filtered = MOCK_ALERTS
        if severity != 'all':
            filtered = [a for a in filtered if a['severity'] == severity]
        if status != 'all':
            filtered = [a for a in filtered if a['status'] == status]
        
        serializer = AlertSerializer(filtered, many=True)
        return Response({
            "data": serializer.data,
            "stats": ALERT_STATS
        })

class AlertRulesView(APIView):
    def get(self, request):
        serializer = AlertRuleSerializer(MOCK_ALERT_RULES, many=True)
        return Response(serializer.data)

class IncidentsView(APIView):
    def get(self, request):
        status = request.query_params.get('status', 'all')
        
        filtered = MOCK_INCIDENTS
        if status != 'all':
            filtered = [i for i in filtered if i['status'] == status]
        
        serializer = IncidentSerializer(filtered, many=True)
        return Response({
            "data": serializer.data,
            "stats": INCIDENT_STATS
        })

class IncidentDetailView(APIView):
    def get(self, request, incident_id):
        incident = next((i for i in MOCK_INCIDENTS if i['id'] == incident_id), None)
        if incident:
            serializer = IncidentSerializer(incident)
            return Response(serializer.data)
        return Response({"error": "Incident not found"}, status=status.HTTP_404_NOT_FOUND)

class AnomaliesView(APIView):
    def get(self, request):
        severity = request.query_params.get('severity', 'all')
        
        filtered = MOCK_ANOMALIES
        if severity != 'all':
            filtered = [a for a in filtered if a['severity'] == severity]
        
        serializer = AnomalySerializer(filtered, many=True)
        return Response({
            "data": serializer.data,
            "stats": ANOMALY_STATS
        })

class AnomalyDetailView(APIView):
    def get(self, request, anomaly_id):
        anomaly = next((a for a in MOCK_ANOMALIES if a['id'] == anomaly_id), None)
        if anomaly:
            serializer = AnomalySerializer(anomaly)
            return Response(serializer.data)
        return Response({"error": "Anomaly not found"}, status=status.HTTP_404_NOT_FOUND)

class ServersView(APIView):
    def get(self, request):
        serializer = ServerSerializer(MOCK_SERVERS, many=True)
        return Response({
            "data": serializer.data,
            "stats": INFRA_STATS
        })

class ThreatsView(APIView):
    def get(self, request):
        serializer = ThreatSerializer(MOCK_THREATS, many=True)
        return Response({
            "data": serializer.data,
            "stats": THREAT_STATS
        })

class ThreatFeedsView(APIView):
    def get(self, request):
        return Response(MOCK_THREAT_FEEDS)

class AIModelsView(APIView):
    def get(self, request):
        serializer = AIModelSerializer(MOCK_AI_MODELS, many=True)
        return Response({
            "data": serializer.data,
            "stats": AI_STATS
        })

class RecentAnalysesView(APIView):
    def get(self, request):
        return Response(MOCK_RECENT_ANALYSES)
