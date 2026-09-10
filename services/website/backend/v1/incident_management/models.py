"""安全事件处置领域模型。

数据边界（见 document/myself/AuditWeaver-项目交接执行规格.md）：
- 原始日志、规则命中、AI 原始分析结果 → Elasticsearch（海量检索/聚合）
- 事件、负责人、状态、处置时间线、Agent 建议快照 → MySQL（事务、关系、审计）

Incident 是分析师基于 ES 检测事件（external_event_id 对应 ES event_id）
创建的处置工单；IncidentTimeline 是事件的审计时间线，状态/负责人变更
由服务层自动写入，不依赖前端提交。
"""

from django.conf import settings
from django.db import models


class Incident(models.Model):
    """安全事件处置工单。"""

    class Status(models.TextChoices):
        OPEN = 'open', '待处理'
        INVESTIGATING = 'investigating', '调查中'
        RESOLVED = 'resolved', '已解决'
        CLOSED = 'closed', '已关闭'

    class Severity(models.TextChoices):
        LOW = 'low', '低危'
        MEDIUM = 'medium', '中危'
        HIGH = 'high', '高危'
        CRITICAL = 'critical', '严重'

    # 合法状态流转：open → investigating → resolved → closed；
    # resolved → investigating 为复开；closed 为终态。
    # open → closed 等跨级流转一律禁止（在服务层/序列化层校验）。
    ALLOWED_TRANSITIONS: dict[str, set[str]] = {
        Status.OPEN: {Status.INVESTIGATING},
        Status.INVESTIGATING: {Status.RESOLVED},
        Status.RESOLVED: {Status.CLOSED, Status.INVESTIGATING},
        Status.CLOSED: set(),
    }

    # 对应 AI 分析报告的 event_id；一个检测事件最多创建一个处置工单
    external_event_id = models.CharField(
        '外部事件ID', max_length=128, unique=True, db_index=False,
    )
    title = models.CharField('标题', max_length=255)
    severity = models.CharField(
        '严重等级', max_length=16, choices=Severity.choices, default=Severity.MEDIUM,
    )
    status = models.CharField(
        '状态', max_length=16, choices=Status.choices, default=Status.OPEN,
    )

    # 从分析报告冗余的摘要字段，避免列表页回查
    source_ip = models.GenericIPAddressField('源IP', null=True, blank=True)
    source_path = models.CharField('请求路径', max_length=2048, blank=True, default='')

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_incidents',
        verbose_name='负责人',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_incidents',
        verbose_name='创建人',
    )

    # Agent 调查建议快照（由 Django 调用内部 Agent Service 后落库）
    agent_summary = models.TextField('Agent分析摘要', blank=True, default='')
    agent_recommendations = models.JSONField(
        'Agent处置建议', default=list, blank=True,
    )
    agent_analyzed_at = models.DateTimeField('Agent分析时间', null=True, blank=True)

    # 乐观锁版本号，服务层每次更新 +1
    version = models.PositiveIntegerField('版本号', default=1)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '安全事件'
        verbose_name_plural = '安全事件'
        ordering = ['-created_at']
        indexes = [
            # 工作台筛选：status / severity 过滤 + 按创建时间倒序
            models.Index(
                fields=['status', 'severity', '-created_at'],
                name='idx_inc_workbench',
            ),
            # “我待处理的事件”：按负责人 + 状态查询
            models.Index(fields=['assignee', 'status'], name='idx_inc_assignee'),
        ]

    def __str__(self) -> str:
        return f'[{self.id}] {self.title} ({self.status})'

    def can_transition_to(self, new_status: str) -> bool:
        """状态机校验：new_status 是否是当前状态允许的下一状态。"""
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    def has_disposition_record(self) -> bool:
        """是否存在人工处置记录。

        critical 事件关闭前必须至少有一条非系统（created）的时间线，
        即分析师真正做过处置/评论，防止高危事件被直接关闭。
        """
        return self.timeline.exclude(
            action=IncidentTimeline.Action.CREATED,
        ).exists()


class IncidentTimeline(models.Model):
    """事件处置时间线（审计流水，只增不改）。"""

    class Action(models.TextChoices):
        CREATED = 'created', '创建事件'
        ASSIGNED = 'assigned', '指派负责人'
        STATUS_CHANGED = 'status_changed', '状态变更'
        COMMENT = 'comment', '处置记录'
        AGENT_ANALYZED = 'agent_analyzed', 'Agent分析'

    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='timeline',
        verbose_name='所属事件',
    )
    action = models.CharField('动作', max_length=32, choices=Action.choices)
    content = models.TextField('内容', default='', blank=True)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='incident_timelines',
        verbose_name='操作人',
    )
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '事件时间线'
        verbose_name_plural = '事件时间线'
        ordering = ['created_at']
        indexes = [
            # 事件详情页按时间正序拉取时间线
            models.Index(fields=['incident', 'created_at'], name='idx_timeline_inc'),
        ]

    def __str__(self) -> str:
        return f'Incident#{self.incident_id} {self.action} @ {self.created_at}'
