"""reports 应用路由（路径与迁移前 api 应用完全一致）。"""
from django.urls import path

from . import views

urlpatterns = [
    path('dashboard/threat-distribution/', views.ThreatDistributionView.as_view(), name='threat_distribution'),
    path('dashboard/recent-alerts/', views.RecentAlertsView.as_view(), name='recent_alerts'),
    path('reports/stats/', views.ReportStatsView.as_view(), name='report_stats'),
    path('reports/list/', views.ReportListView.as_view(), name='report_list'),
    path('reports/<str:report_id>/', views.ReportDetailView.as_view(), name='report_detail'),
    # 审核闭环：认领 / 释放 / 提交改判 / 历史流水
    path('reports/<str:report_id>/claim/', views.ReportClaimView.as_view(), name='report_claim'),
    path('reports/<str:report_id>/release/', views.ReportReleaseView.as_view(), name='report_release'),
    path('reports/<str:report_id>/review/', views.ReportReviewView.as_view(), name='report_review'),
    path('reports/<str:report_id>/review/history/', views.ReviewHistoryView.as_view(), name='review_history'),
]
