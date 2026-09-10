"""reports 应用 Admin：报告审核列只读；审核结论/历史全只读（审计数据不在 Admin 修改）。"""
from django.contrib import admin

from .models import AnalysisReport, ReportReview, ReportReviewHistory


@admin.register(AnalysisReport)
class AnalysisReportAdmin(admin.ModelAdmin):
    """AI 分析报告：raw 字段折叠只读，审核/认领列只读。"""

    list_display = (
        'event_id', 'attack_type_ai', 'risk_level', 'review_status',
        'reviewed_by', 'claimed_by', 'analysis_timestamp',
    )
    list_filter = ('review_status', 'risk_level')
    search_fields = ('event_id', 'ip', 'path', 'attack_type_ai')
    readonly_fields = (
        'review_status', 'reviewed_by', 'reviewed_at',
        'claimed_by', 'claimed_at',
    )
    fieldsets = (
        ('事件', {'fields': ('event_id', 'ip', 'path', 'method', 'status', 'user_agent',
                             'detect_type')}),
        ('AI 分析', {'fields': ('risk_level', 'risk_score', 'attack_type_ai', 'summary',
                                'reasoning', 'recommendations')}),
        ('时间', {'fields': ('log_timestamp', 'analysis_timestamp', 'ingestion_time')}),
        ('存档', {'classes': ('collapse',),
                  'fields': ('raw_response', 'original_log')}),
        ('人工审核（只读）', {'fields': ('review_status', 'reviewed_by', 'reviewed_at',
                                        'claimed_by', 'claimed_at')}),
    )


@admin.register(ReportReview)
class ReportReviewAdmin(admin.ModelAdmin):
    """审核当前结论：全只读。"""

    list_display = ('report', 'verdict', 'category', 'reviewer', 'updated_at')
    list_filter = ('verdict', 'category')
    search_fields = ('report__event_id',)
    readonly_fields = [f.name for f in ReportReview._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReportReviewHistory)
class ReportReviewHistoryAdmin(admin.ModelAdmin):
    """审核历史流水：全只读（append-only 审计）。"""

    list_display = ('report', 'change_type', 'verdict', 'category', 'reviewer', 'created_at')
    list_filter = ('change_type', 'verdict')
    search_fields = ('report__event_id',)
    readonly_fields = [f.name for f in ReportReviewHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
