"""AI 安全分析报告领域模型。

数据由 services/agent 管线在 LLM 分析成功后直接写入本表（UPSERT，
键为 event_id），替代原 Elasticsearch ``log_analysis_reports`` 索引。

数据边界：
- AI 结构化分析报告 → MySQL（本表）
- 原始访问日志（nginx-log-raw）、规则命中（matched_logs）、死信 → Elasticsearch

一份报告对应一个 event_id；同 event_id 重复分析时整行覆盖（与 ES 既有行为一致）。
报告详情页所需的"原始日志行"（event.original）仍在 ES nginx-log-raw，
本表 ``original_log`` 仅保存规则引擎消息快照。
"""
from django.db import models


class AnalysisReport(models.Model):
    """AI 安全分析报告（原 ES log_analysis_reports 索引）。"""

    class RiskLevel(models.TextChoices):
        CRITICAL = 'critical', '严重'
        HIGH = 'high', '高危'
        MEDIUM = 'medium', '中危'
        LOW = 'low', '低危'
        NORMAL = 'normal', '正常'
        UNKNOWN = 'unknown', '未知'

    event_id = models.CharField('事件ID', max_length=128, unique=True)
    ip = models.GenericIPAddressField('源IP', null=True, blank=True)
    path = models.CharField('请求路径', max_length=2048, default='', blank=True)
    method = models.CharField('HTTP方法', max_length=16, default='', blank=True)
    status = models.IntegerField('HTTP状态码', null=True, blank=True)
    user_agent = models.CharField('User-Agent', max_length=1024, default='', blank=True)
    detect_type = models.CharField(
        '规则攻击类型', max_length=64, default='', blank=True, db_index=True,
    )

    risk_level = models.CharField(
        '风险等级', max_length=16, choices=RiskLevel.choices,
        default=RiskLevel.UNKNOWN, db_index=True,
    )
    risk_score = models.IntegerField('风险评分', default=0)
    attack_type_ai = models.CharField(
        'AI攻击类型', max_length=64, default='', blank=True, db_index=True,
    )
    summary = models.TextField('分析摘要', default='', blank=True)
    reasoning = models.JSONField('推理过程', default=list, blank=True)
    recommendations = models.JSONField('处置建议', default=list, blank=True)

    log_timestamp = models.DateTimeField('日志时间', null=True, blank=True)
    analysis_timestamp = models.DateTimeField('分析时间', db_index=True)
    ingestion_time = models.DateTimeField('摄入时间', db_index=True)

    # 原 ES dify_response / original_log（mapping enabled:false 的存档字段）
    raw_response = models.JSONField('LLM原始响应', null=True, blank=True, default=None)
    original_log = models.JSONField('原始消息快照', null=True, blank=True, default=None)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'analysis_report'
        verbose_name = 'AI分析报告'
        verbose_name_plural = 'AI分析报告'
        ordering = ['-analysis_timestamp']
        indexes = [
            models.Index(fields=['risk_level', '-analysis_timestamp'], name='idx_report_risk_ts'),
            models.Index(fields=['ip', '-analysis_timestamp'], name='idx_report_ip_ts'),
        ]

    def __str__(self) -> str:
        return f'[{self.event_id}] {self.attack_type_ai} ({self.risk_level})'
