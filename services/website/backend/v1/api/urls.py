from django.urls import path, include
from .views import (
    HealthCheckView,
    DashboardStatsView,
    ThreatDistributionView,
    LogsView,
    LogStatsView,
    LogTrendView,
    AlertsView,
    AlertRulesView,
    IncidentsView,
    IncidentDetailView,
    AnomaliesView,
    AnomalyDetailView,
    ServersView,
    ThreatsView,
    ThreatFeedsView,
    AIModelsView,
    RecentAnalysesView,
    RecentAlertsView,
    ReportStatsView,
    ReportListView,
    ReportDetailView,
    AgentProxyView,
)

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health_check'),
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard_stats'),
    path('dashboard/threat-distribution/', ThreatDistributionView.as_view(), name='threat_distribution'),

    path('logs/', LogsView.as_view(), name='logs'),
    path('logs/stats/', LogStatsView.as_view(), name='log_stats'),
    path('logs/trend/', LogTrendView.as_view(), name='log_trend'),

    path('alerts/', AlertsView.as_view(), name='alerts'),
    path('alerts/rules/', AlertRulesView.as_view(), name='alert_rules'),

    path('incidents/', IncidentsView.as_view(), name='incidents'),
    path('incidents/<str:incident_id>/', IncidentDetailView.as_view(), name='incident_detail'),

    path('anomalies/', AnomaliesView.as_view(), name='anomalies'),
    path('anomalies/<str:anomaly_id>/', AnomalyDetailView.as_view(), name='anomaly_detail'),

    path('infrastructure/servers/', ServersView.as_view(), name='servers'),

    path('threats/', ThreatsView.as_view(), name='threats'),
    path('threats/feeds/', ThreatFeedsView.as_view(), name='threat_feeds'),

    path('ai/models/', AIModelsView.as_view(), name='ai_models'),
    path('ai/analyses/', RecentAnalysesView.as_view(), name='recent_analyses'),

    path('dashboard/recent-alerts/', RecentAlertsView.as_view(), name='recent_alerts'),
    path('reports/stats/', ReportStatsView.as_view(), name='report_stats'),
    path('reports/list/', ReportListView.as_view(), name='report_list'),
    path('reports/<str:report_id>/', ReportDetailView.as_view(), name='report_detail'),

    # Agent Service 反代(Django → 内部 FastAPI :8001)
    # agent_type 作为路径变量,一版合法值:analysis_explorer;新增 agent 无需改此路由
    path('agent/<str:agent_type>/chat', AgentProxyView.as_view(), name='agent_chat'),
    path('agent/<str:agent_type>/chat/sync', AgentProxyView.as_view(), name='agent_chat_sync'),
    path('agent/health', AgentProxyView.as_view(), name='agent_health'),
    path('agent/types', AgentProxyView.as_view(), name='agent_types'),
]

# Accounts(登录鉴权)
urlpatterns += [
    path('', include('accounts.urls')),
]