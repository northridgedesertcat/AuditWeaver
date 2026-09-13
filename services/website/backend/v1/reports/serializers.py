"""报告审核序列化器：写入校验（枚举/长度/软校验）与读取输出（中文标签 + 本地化时间）。"""
from django.utils import timezone
from rest_framework import serializers

from .models import ReportReview, ReportReviewHistory


def _local_str(dt):
    """UTC datetime → 本地时区格式化字符串（契约同旧 format_timestamp）。"""
    if not dt:
        return None
    return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M:%S')


# 处置动作字典（与前端 lib/review-options.ts 的 code 对齐，标签各自维护）
ACTION_CHOICES = [
    'ignored', 'observed', 'ip_blocked', 'waf_rule_added',
    'incident_created', 'notified', 'other',
]
ACTION_LABELS = {
    'ignored': '忽略/关闭',
    'observed': '持续观察',
    'ip_blocked': '已封禁 IP',
    'waf_rule_added': '已加 WAF/检测规则',
    'incident_created': '已转处置工单',
    'notified': '已通知相关方',
    'other': '其他',
}

# 软校验：verdict=uncertain 时 actions 仅允许这些取值
UNCERTAIN_ALLOWED_ACTIONS = {'observed', 'ignored', 'other'}


class ReviewWriteSerializer(serializers.Serializer):
    """提交/改判审核的输入校验。reviewer 一律取认证用户，不接受请求体传入。"""

    verdict = serializers.ChoiceField(
        choices=ReportReview.Verdict.values,
        error_messages={'invalid_choice': '无效的报告正确性取值'},
    )
    category = serializers.ChoiceField(
        choices=ReportReview.Category.values,
        error_messages={'invalid_choice': '无效的实际情况取值'},
    )
    actions = serializers.ListField(
        child=serializers.ChoiceField(choices=ACTION_CHOICES,
                                      error_messages={'invalid_choice': '无效的处置动作：{input}'}),
        max_length=7, required=False, default=list,
    )
    comment = serializers.CharField()

    def validate_comment(self, value):
        """去空格后至少 5 字符，强制留痕。"""
        stripped = value.strip()
        if len(stripped) < 5:
            raise serializers.ValidationError('处理说明至少需要 5 个字符')
        return stripped

    def validate_actions(self, value):
        """去重保序。"""
        seen = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return seen

    def validate(self, attrs):
        """软校验：无法判定时不允许确定性处置动作（仅序列化层约束，不做 DB 约束）。"""
        if attrs.get('verdict') == ReportReview.Verdict.UNCERTAIN:
            bad = [a for a in attrs.get('actions', []) if a not in UNCERTAIN_ALLOWED_ACTIONS]
            if bad:
                raise serializers.ValidationError(
                    {'actions': '无法判定时处置动作仅允许：持续观察/忽略/其他'})
        return attrs


class ReviewReadSerializer(serializers.Serializer):
    """审核当前结论输出（首次/改判共用；changeType 由视图按场景传入）。"""

    verdict = serializers.CharField()
    verdictLabel = serializers.SerializerMethodField()
    category = serializers.CharField()
    categoryLabel = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    actionLabels = serializers.SerializerMethodField()
    comment = serializers.CharField()
    reviewer = serializers.SerializerMethodField()
    reviewerDisplayName = serializers.SerializerMethodField()
    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()
    changeType = serializers.SerializerMethodField()

    def get_verdictLabel(self, obj):
        return ReportReview.Verdict(obj.verdict).label

    def get_categoryLabel(self, obj):
        return ReportReview.Category(obj.category).label

    def get_actions(self, obj):
        return obj.actions or []

    def get_actionLabels(self, obj):
        return [ACTION_LABELS[a] for a in (obj.actions or []) if a in ACTION_LABELS]

    def get_reviewer(self, obj):
        return obj.reviewer.username if obj.reviewer else None

    def get_reviewerDisplayName(self, obj):
        if not obj.reviewer:
            return None
        return obj.reviewer.display_name or obj.reviewer.username

    def get_createdAt(self, obj):
        return _local_str(obj.created_at)

    def get_updatedAt(self, obj):
        return _local_str(obj.updated_at)

    def get_changeType(self, obj):
        return self.context.get('change_type', 'created')


class HistorySerializer(serializers.Serializer):
    """审核历史流水输出（append-only 快照，最新在前由视图 ordering 保证）。"""

    changeType = serializers.CharField(source='change_type')
    verdict = serializers.CharField()
    verdictLabel = serializers.SerializerMethodField()
    category = serializers.CharField()
    categoryLabel = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    actionLabels = serializers.SerializerMethodField()
    comment = serializers.CharField()
    reviewer = serializers.SerializerMethodField()
    reviewerDisplayName = serializers.SerializerMethodField()
    createdAt = serializers.SerializerMethodField()

    def get_verdictLabel(self, obj):
        return ReportReview.Verdict(obj.verdict).label

    def get_categoryLabel(self, obj):
        return ReportReview.Category(obj.category).label

    def get_actions(self, obj):
        return obj.actions or []

    def get_actionLabels(self, obj):
        return [ACTION_LABELS[a] for a in (obj.actions or []) if a in ACTION_LABELS]

    def get_reviewer(self, obj):
        return obj.reviewer.username if obj.reviewer else None

    def get_reviewerDisplayName(self, obj):
        if not obj.reviewer:
            return None
        return obj.reviewer.display_name or obj.reviewer.username

    def get_createdAt(self, obj):
        return _local_str(obj.created_at)
