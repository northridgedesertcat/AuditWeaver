"""AI 分析报告视图（原 api 应用中基于 ES log_analysis_reports 的 5 个视图）。

数据已迁移至 MySQL ``analysis_report`` 表（本应用 models），响应契约保持不变：
- riskLevel 仍为小写；id 仍为 event_id（= 原 ES _id）；
- generatedAt 仍为本地时区格式化字符串；recent-alerts 的 time 仍为毫秒时间戳。

唯一保留的 ES 依赖：报告详情页的"原始日志行"（event.original）
仍查 nginx-log-raw 索引（D12）。
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from common.env import ES_INDEX_NGINX_RAW
from common.time_utils import to_epoch_millis

from .models import AnalysisReport, ReportReview, ReportReviewHistory
from .serializers import ReviewReadSerializer, ReviewWriteSerializer, HistorySerializer

# 报告详情所需"原始日志行"仍在 ES（nginx-log-raw）
from api.es_client import is_es_available, get_es_client

# 认领超时（惰性过期，无需定时任务）：判断时点在认领/提交时比较 claimed_at
CLAIM_TTL = timedelta(minutes=30)

# 列表排序白名单：禁止 query 参数直拼 order_by
ORDERING_WHITELIST = {
    '-analysis_timestamp', 'analysis_timestamp', '-risk_score', '-reviewed_at',
}


def _today_start_utc():
    """UTC 今日零点（与旧 ES 视图 now_utc().replace(hour=0,...) 语义一致）。"""
    return timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)


def _format_local(dt):
    """UTC datetime → 本地时区格式化字符串（契约同旧 format_timestamp）。"""
    if not dt:
        return '未知时间'
    return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M:%S')


def _display_name(user):
    """用户展示名（display_name 优先，兜底 username；用户被删后返回占位）。"""
    if user is None:
        return '未知用户'
    return user.display_name or user.username


def _is_claim_active(report, user_id, now):
    """报告是否处于『他人有效认领』状态（行锁内调用）。"""
    return (
        report.review_status == AnalysisReport.ReviewStatus.CLAIMED
        and report.claimed_by_id != user_id
        and report.claimed_at is not None
        and now - report.claimed_at < CLAIM_TTL
    )


def _next_pending_event_id(exclude_event_id):
    """下一条可处理报告：pending 优先，其次超时 claimed；排除他人未超时认领。

    排序与工作台待处理队列一致：AI 风险评分降序 + 分析时间倒序。
    """
    now = timezone.now()
    return (
        AnalysisReport.objects
        .filter(
            Q(review_status=AnalysisReport.ReviewStatus.PENDING)
            | Q(review_status=AnalysisReport.ReviewStatus.CLAIMED,
                claimed_at__lt=now - CLAIM_TTL)
        )
        .exclude(event_id=exclude_event_id)
        .order_by('-risk_score', '-analysis_timestamp')
        .values_list('event_id', flat=True)
        .first()
    )


class ThreatDistributionView(APIView):
    """威胁等级分布：按 analysis_report.risk_level 聚合。

    风险等级在库中以小写存储（critical/high/medium/low/normal/unknown），
    响应仍返回首字母大写的五档结构（Critical/High/Medium/Low/Normal）。
    unknown 与 ES 旧逻辑一致并入 Low 档。
    """

    def get(self, request):
        all_levels = ['Critical', 'High', 'Medium', 'Low', 'Normal']
        level_color_map = {
            'Critical': 'oklch(0.5 0.25 25)',
            'High': 'oklch(0.65 0.2 60)',
            'Medium': 'oklch(0.75 0.15 95)',
            'Low': 'oklch(0.75 0.12 145)',
            'Normal': 'oklch(0.7 0.05 260)',
        }
        level_label_map = {
            'Critical': '严重',
            'High': '高危',
            'Medium': '中危',
            'Low': '低危',
            'Normal': '正常',
        }
        distribution = {
            level: {
                'name': level_label_map[level],
                'value': 0,
                'color': level_color_map[level],
            }
            for level in all_levels
        }

        time_range = request.query_params.get('range', 'all')

        qs = AnalysisReport.objects.all()
        if time_range == 'today':
            qs = qs.filter(analysis_timestamp__gte=_today_start_utc())

        # 小写存储 → 大写响应键；unknown 并入 Low（与旧 ES 视图一致）
        level_key_map = {
            'critical': 'Critical',
            'high': 'High',
            'medium': 'Medium',
            'low': 'Low',
            'normal': 'Normal',
            'unknown': 'Low',
        }
        for row in qs.values('risk_level').annotate(c=Count('id')):
            level_key = level_key_map.get((row['risk_level'] or '').lower())
            if level_key in distribution:
                distribution[level_key]['value'] += row['c']

        total = sum(item['value'] for item in distribution.values())
        return Response({'data': distribution, 'total': total, 'range': time_range})


class RecentAlertsView(APIView):
    """最近告警：analysis_report 最新 10 条（按 ingestion_time 倒序）。"""

    def get(self, request):
        alerts = []
        for report in AnalysisReport.objects.order_by('-ingestion_time')[:10]:
            alerts.append({
                'id': report.event_id,
                'severity': (report.risk_level or 'unknown').lower(),
                'message': f"检测到可疑{report.attack_type_ai or '未知攻击'}",
                'source': 'AI Security Analyzer',
                # 契约：time 为毫秒时间戳
                'time': to_epoch_millis(report.ingestion_time),
                'ip': report.ip or '未知IP',
            })
        return Response({'data': alerts})


class ReportStatsView(APIView):
    """报告统计：total / highRisk(critical+high) / mediumRisk / todayNew + 审核三键。"""

    def get(self, request):
        qs = AnalysisReport.objects.all()
        stats = {
            'total': qs.count(),
            'highRisk': qs.filter(risk_level__in=['critical', 'high']).count(),
            'mediumRisk': qs.filter(risk_level='medium').count(),
            'todayNew': qs.filter(analysis_timestamp__gte=_today_start_utc()).count(),
            # 审核闭环新增：待处理数 / 处理中数 / 今日处理完成数
            'pendingReview': qs.filter(review_status=AnalysisReport.ReviewStatus.PENDING).count(),
            'claimedCount': qs.filter(review_status=AnalysisReport.ReviewStatus.CLAIMED).count(),
            'todayProcessed': qs.filter(
                review_status=AnalysisReport.ReviewStatus.PROCESSED,
                reviewed_at__gte=_today_start_utc(),
            ).count(),
        }
        # TODO(P1): invalidate report stats cache（接入 Redis 后按 Cache-Aside 失效）
        return Response(stats)


class ReportListView(APIView):
    """报告列表：分页 + risk_level / attack_type / keyword / review_status 过滤。

    keyword 走 MySQL LIKE（D11），匹配 attack_type_ai / ip / path。
    ordering 白名单：-analysis_timestamp（默认）/analysis_timestamp/-risk_score/-reviewed_at。
    """

    def get(self, request):
        params = request.query_params
        try:
            page = int(params.get('page', 1))
            size = int(params.get('size', 10))
        except (TypeError, ValueError):
            return Response({'error': 'page/size 必须为整数'}, status=status.HTTP_400_BAD_REQUEST)

        risk_level = params.get('risk_level', None)
        attack_type = params.get('attack_type', None)
        keyword = params.get('keyword', None)
        review_status = params.get('review_status', None)
        reviewed_by = params.get('reviewed_by', None)
        ordering = params.get('ordering', '-analysis_timestamp')

        if ordering not in ORDERING_WHITELIST:
            return Response({'error': '非法的排序字段'}, status=status.HTTP_400_BAD_REQUEST)
        if review_status and review_status not in AnalysisReport.ReviewStatus.values:
            return Response({'error': '非法的处理状态'}, status=status.HTTP_400_BAD_REQUEST)

        qs = AnalysisReport.objects.select_related('reviewed_by', 'claimed_by')

        if risk_level and risk_level != 'all':
            # 库中小写存储；前端传小写或首字母大写都归一
            qs = qs.filter(risk_level=risk_level.lower())

        if attack_type and attack_type != 'all':
            qs = qs.filter(attack_type_ai=attack_type)

        if keyword:
            qs = qs.filter(
                Q(attack_type_ai__icontains=keyword)
                | Q(ip__icontains=keyword)
                | Q(path__icontains=keyword)
            )

        if review_status:
            qs = qs.filter(review_status=review_status)

        # reviewed_by=me：当前用户处理过的（工作台「已处理」tab 用；仅支持字面量 me）
        if reviewed_by == 'me':
            qs = qs.filter(reviewed_by=request.user)

        total = qs.count()
        reports = []
        for report in qs.order_by(ordering)[(page - 1) * size: page * size]:
            processed = report.review_status == AnalysisReport.ReviewStatus.PROCESSED
            reports.append({
                'id': report.event_id,
                'title': f"检测到{report.attack_type_ai or '未知攻击'}",
                'riskLevel': (report.risk_level or 'unknown').lower(),
                'attackType': report.attack_type_ai or '未知攻击',
                'sourceIp': report.ip or '未知IP',
                'targetPath': report.path or '未知路径',
                'generatedAt': _format_local(report.analysis_timestamp),
                'aiConfidence': report.risk_score or 0,
                # 处理状态（新）：三态 + 冗余处理人/认领人展示名
                'reviewStatus': report.review_status,
                'reviewedBy': _display_name(report.reviewed_by) if report.reviewed_by else None,
                'reviewedAt': _format_local(report.reviewed_at) if report.reviewed_at else None,
                'claimedBy': _display_name(report.claimed_by) if report.claimed_by else None,
                'claimedAt': _format_local(report.claimed_at) if report.claimed_at else None,
                # 旧契约 status 保留一个版本周期：对齐前端现有 statusConfig，前端切换后移除
                'status': 'resolved' if processed else 'pending',
            })

        # TODO(P1): invalidate report list cache（接入 Redis 后按 Cache-Aside 失效）
        return Response({
            'data': reports,
            'total': total,
            'page': page,
            'size': size,
        })


class ReportDetailView(APIView):
    """报告详情：按 event_id 取 analysis_report。

    originalRiskData.original_log（原始日志行 event.original）仍查
    ES nginx-log-raw（D12）；ES 不可用时返回空字符串，不影响详情主体。
    """

    def get(self, request, report_id):
        report = (
            AnalysisReport.objects
            .select_related('review', 'review__reviewer', 'reviewed_by', 'claimed_by')
            .filter(event_id=report_id)
            .first()
        )
        if report is None:
            return Response(
                {'error': 'Report not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        attack_type = report.attack_type_ai or report.detect_type or '未知攻击'

        # 原始日志行：查 ES nginx-log-raw（迁移后报告链路唯一 ES 依赖）
        original_log_content = ''
        if is_es_available():
            try:
                es = get_es_client()
                if es:
                    log_result = es.search(
                        index=ES_INDEX_NGINX_RAW,
                        body={
                            'query': {'match': {'event_id': report.event_id}},
                            'size': 1,
                        },
                    )
                    hits = log_result.get('hits', {}).get('hits', [])
                    if hits:
                        original_log_content = (
                            hits[0].get('_source', {}).get('event', {}).get('original', '')
                        )
            except Exception:
                pass

        original_risk_data = {
            'event_id': report.event_id,
            'ip': report.ip or '',
            'log_timestamp': _format_local(report.log_timestamp),
            'user_agent': report.user_agent or '',
            'status': report.status if report.status is not None else 0,
            'path': report.path or '',
            'original_log': original_log_content,
        }

        # ---- 审核增量：当前结论 + 认领/处理信息（未处理时 review 为 null）----
        # select_related 反向 O2O 缺失时访问属性抛 RelatedObjectDoesNotExist
        # （AttributeError 子类），故用 getattr 取值
        review_obj = getattr(report, 'review', None)
        review_payload = None
        if review_obj is not None:
            # changeType 取最新一条流水（created=首次审核 / revised=改判）
            latest_history = (
                ReportReviewHistory.objects
                .filter(report=report).only('change_type').first()
            )
            review_payload = ReviewReadSerializer(
                review_obj,
                context={'change_type': latest_history.change_type if latest_history else 'created'},
            ).data

        return Response({
            'id': report.event_id,
            'title': f"检测到{attack_type}",
            'riskLevel': (report.risk_level or 'unknown').lower(),
            'attackType': attack_type,
            'confidence': report.risk_score or 0,
            'riskScore': report.risk_score or 0,
            'generatedAt': _format_local(report.analysis_timestamp),
            'summary': report.summary or '',
            'reasoning': report.reasoning or [],
            'recommendations': report.recommendations or [],
            'originalRiskData': original_risk_data,
            'reviewStatus': report.review_status,
            'claimedBy': _display_name(report.claimed_by) if report.claimed_by else None,
            'claimedAt': _format_local(report.claimed_at) if report.claimed_at else None,
            'reviewedBy': _display_name(report.reviewed_by) if report.reviewed_by else None,
            'reviewedAt': _format_local(report.reviewed_at) if report.reviewed_at else None,
            'review': review_payload,
        })


class ReportClaimView(APIView):
    """认领报告（轻量协作锁）：pending → claimed；自己重复认领幂等；超时可接管。"""

    def post(self, request, report_id):
        with transaction.atomic():
            report = (
                AnalysisReport.objects.select_for_update()
                .filter(event_id=report_id).first()
            )
            if report is None:
                return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)
            if report.review_status == AnalysisReport.ReviewStatus.PROCESSED:
                return Response(
                    {'error': '报告已处理完成，改判请直接提交审核'},
                    status=status.HTTP_409_CONFLICT,
                )

            now = timezone.now()
            taken_over = False
            if report.review_status == AnalysisReport.ReviewStatus.CLAIMED:
                if report.claimed_by_id == request.user.id:
                    pass  # 自己重复认领：幂等成功，认领时间不刷新
                elif report.claimed_at is not None and now - report.claimed_at < CLAIM_TTL:
                    return Response(
                        {'error': f'报告已被 {_display_name(report.claimed_by)} 认领处理中'},
                        status=status.HTTP_409_CONFLICT,
                    )
                else:
                    taken_over = True  # 超时接管

            if taken_over or report.review_status != AnalysisReport.ReviewStatus.CLAIMED:
                report.review_status = AnalysisReport.ReviewStatus.CLAIMED
                report.claimed_by = request.user
                report.claimed_at = now
                report.save(update_fields=['review_status', 'claimed_by', 'claimed_at',
                                           'updated_at'])
            # TODO(P1): invalidate report list/stats cache

        return Response({
            'reviewStatus': 'claimed',
            'claimedBy': _display_name(request.user),
            'takenOver': taken_over,
        })


class ReportReleaseView(APIView):
    """释放认领：claimed → pending，清空认领字段；仅认领人本人可释放。"""

    def post(self, request, report_id):
        with transaction.atomic():
            report = (
                AnalysisReport.objects.select_for_update()
                .filter(event_id=report_id).first()
            )
            if report is None:
                return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)
            if report.review_status != AnalysisReport.ReviewStatus.CLAIMED:
                return Response(
                    {'error': '报告不在处理中状态'}, status=status.HTTP_409_CONFLICT)
            if report.claimed_by_id != request.user.id:
                # 防误操作；超时接管请走 claim
                return Response(
                    {'error': '只有认领人可以释放认领'}, status=status.HTTP_403_FORBIDDEN)

            report.review_status = AnalysisReport.ReviewStatus.PENDING
            report.claimed_by = None
            report.claimed_at = None
            report.save(update_fields=['review_status', 'claimed_by', 'claimed_at',
                                       'updated_at'])
            # TODO(P1): invalidate report list/stats cache

        return Response({'reviewStatus': 'pending'})


class ReportReviewView(APIView):
    """提交/改判审核：行锁内状态检查 → 当前态 update_or_create + 流水 append（同事务双写）。

    - pending 允许直接提交（宽容设计）；claimed 仅认领人（或超时后任何人）可提交；
      processed 改判免认领。
    - reviewer 取自认证用户，请求体不可伪造。
    """

    def post(self, request, report_id):
        serializer = ReviewWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            report = (
                AnalysisReport.objects.select_for_update()
                .select_related('review')
                .filter(event_id=report_id).first()
            )
            if report is None:
                return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)

            now = timezone.now()
            if _is_claim_active(report, request.user.id, now):
                return Response(
                    {'error': f'报告已被 {_display_name(report.claimed_by)} 认领处理中'},
                    status=status.HTTP_409_CONFLICT,
                )

            was_processed = report.review_status == AnalysisReport.ReviewStatus.PROCESSED

            # 当前态：一份报告至多一条，改判覆盖
            review, created = ReportReview.objects.update_or_create(
                report=report,
                defaults={
                    'verdict': data['verdict'],
                    'category': data['category'],
                    'actions': data['actions'],
                    'comment': data['comment'],
                    'reviewer': request.user,
                },
            )
            # 流水留痕：首次 created / 改判 revised（任一失败整体回滚）
            ReportReviewHistory.objects.create(
                report=report,
                change_type=(ReportReviewHistory.ChangeType.REVISED if was_processed
                             else ReportReviewHistory.ChangeType.CREATED),
                verdict=data['verdict'],
                category=data['category'],
                actions=data['actions'],
                comment=data['comment'],
                reviewer=request.user,
            )

            report.review_status = AnalysisReport.ReviewStatus.PROCESSED
            report.reviewed_by = request.user
            report.reviewed_at = now
            report.claimed_by = None  # 认领锁随提交释放
            report.claimed_at = None
            report.save(update_fields=['review_status', 'reviewed_by', 'reviewed_at',
                                       'claimed_by', 'claimed_at', 'updated_at'])

            # 事务提交前取下一条可处理报告（供前端流水线自动进入）
            next_event_id = _next_pending_event_id(exclude_event_id=report.event_id)
            # TODO(P1): invalidate report list/stats cache

        payload = ReviewReadSerializer(
            review,
            context={
                'change_type': ('revised' if was_processed else 'created'),
            },
        ).data
        payload = {
            'eventId': report.event_id,
            'reviewStatus': report.review_status,
            'review': payload,
            'nextEventId': next_event_id,
        }
        return Response(payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ReviewHistoryView(APIView):
    """审核历史流水：按分析报告取全部快照，最新在前。"""

    def get(self, request, report_id):
        report = (
            AnalysisReport.objects.only('id', 'event_id')
            .filter(event_id=report_id).first()
        )
        if report is None:
            return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)

        rows = ReportReviewHistory.objects.filter(report=report)
        return Response({
            'eventId': report.event_id,
            'total': rows.count(),
            'history': HistorySerializer(rows, many=True).data,
        })
