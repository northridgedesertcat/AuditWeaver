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
from django.conf import settings
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

    # ---- 人工审核字段（Agent 管线 UPSERT 覆盖清单不含以下列，
    #      同 event_id 重新分析不会冲掉审核/认领状态，测试已锁住该行为）----

    class ReviewStatus(models.TextChoices):
        PENDING = 'pending', '待处理'
        CLAIMED = 'claimed', '处理中'
        PROCESSED = 'processed', '已处理'

    review_status = models.CharField(
        '处理状态', max_length=16,
        choices=ReviewStatus.choices, default=ReviewStatus.PENDING,
        # db_default 写入数据库层 DEFAULT：Agent 管线 UPSERT 的 INSERT 不含本列，
        # 必须依赖 DB 默认值（ORM 级 default 在 MySQL 加列时不生成 DEFAULT 子句）
        db_default='pending',
    )
    reviewed_by = models.ForeignKey(           # 冗余：列表页处理人不 JOIN 审核表
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_reports', verbose_name='处理人',
    )
    reviewed_at = models.DateTimeField('处理时间', null=True, blank=True)
    claimed_by = models.ForeignKey(            # 冗余：工作台列表显示认领人
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='claimed_reports', verbose_name='认领人',
    )
    claimed_at = models.DateTimeField('认领时间', null=True, blank=True)

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
            # 工作台主查询：按状态过滤 + 分析时间倒序（pending/claimed/processed 三态共用）
            models.Index(fields=['review_status', '-analysis_timestamp'],
                         name='idx_report_review_ts'),
        ]

    def __str__(self) -> str:
        return f'[{self.event_id}] {self.attack_type_ai} ({self.risk_level})'


class ReportReview(models.Model):
    """AI 报告人工审核当前结论（一份报告至多一条，改判覆盖）。"""

    class Verdict(models.TextChoices):
        CORRECT = 'correct', '报告正确'
        FALSE_POSITIVE = 'false_positive', '误报'
        PARTIALLY_CORRECT = 'partially_correct', '部分正确'
        UNCERTAIN = 'uncertain', '无法判定'

    class Category(models.TextChoices):
        REAL_ATTACK = 'real_attack', '真实攻击'
        SCANNER_PROBE = 'scanner_probe', '扫描探测'
        NORMAL_BUSINESS = 'normal_business', '正常业务'
        RULE_MISFIRE = 'rule_misfire', '规则误报'
        AI_MISJUDGMENT = 'ai_misjudgment', 'AI误判'
        OTHER = 'other', '其他'

    report = models.OneToOneField(
        AnalysisReport, on_delete=models.CASCADE,
        related_name='review', verbose_name='所属报告',
    )
    verdict = models.CharField('报告正确性', max_length=32, choices=Verdict.choices)
    category = models.CharField('实际情况', max_length=32, choices=Category.choices)
    actions = models.JSONField('处置动作', default=list, blank=True)
    comment = models.TextField('处理说明')
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='report_reviews', verbose_name='处理人',
    )
    created_at = models.DateTimeField('首次处理时间', auto_now_add=True)
    updated_at = models.DateTimeField('最近改判时间', auto_now=True)

    class Meta:
        db_table = 'report_review'
        verbose_name = '报告审核结论'
        verbose_name_plural = '报告审核结论'
        ordering = ['-updated_at']

    def __str__(self) -> str:
        return f'[审核] {self.report_id} {self.verdict}'


class ReportReviewHistory(models.Model):
    """审核结论历史流水（只增不改，改判留痕；视图/Admin 全只读）。"""

    class ChangeType(models.TextChoices):
        CREATED = 'created', '首次审核'
        REVISED = 'revised', '改判'

    report = models.ForeignKey(
        AnalysisReport, on_delete=models.CASCADE,
        related_name='review_history', verbose_name='所属报告',
    )
    change_type = models.CharField('变更类型', max_length=16, choices=ChangeType.choices)
    verdict = models.CharField(max_length=32, choices=ReportReview.Verdict.choices)
    category = models.CharField(max_length=32, choices=ReportReview.Category.choices)
    actions = models.JSONField(default=list, blank=True)
    comment = models.TextField()
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='report_review_histories',
    )
    created_at = models.DateTimeField('结论时间', auto_now_add=True)

    class Meta:
        db_table = 'report_review_history'
        verbose_name = '报告审核历史'
        verbose_name_plural = '报告审核历史'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['report', '-created_at'], name='idx_rrh_report_ts')]

    def __str__(self) -> str:
        return f'[历史] {self.report_id} {self.change_type} {self.verdict}'
