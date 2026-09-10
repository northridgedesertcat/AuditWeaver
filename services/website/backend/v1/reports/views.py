"""AI 分析报告视图（原 api 应用中基于 ES log_analysis_reports 的 5 个视图）。

数据已迁移至 MySQL ``analysis_report`` 表（本应用 models），响应契约保持不变：
- riskLevel 仍为小写；id 仍为 event_id（= 原 ES _id）；
- generatedAt 仍为本地时区格式化字符串；recent-alerts 的 time 仍为毫秒时间戳。

唯一保留的 ES 依赖：报告详情页的"原始日志行"（event.original）
仍查 nginx-log-raw 索引（D12）。
"""
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from common.env import ES_INDEX_NGINX_RAW
from common.time_utils import to_epoch_millis

from .models import AnalysisReport

# 报告详情所需"原始日志行"仍在 ES（nginx-log-raw）
from api.es_client import is_es_available, get_es_client


def _today_start_utc():
    """UTC 今日零点（与旧 ES 视图 now_utc().replace(hour=0,...) 语义一致）。"""
    return timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)


def _format_local(dt):
    """UTC datetime → 本地时区格式化字符串（契约同旧 format_timestamp）。"""
    if not dt:
        return '未知时间'
    return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M:%S')


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
    """报告统计：total / highRisk(critical+high) / mediumRisk(medium) / todayNew。"""

    def get(self, request):
        qs = AnalysisReport.objects.all()
        stats = {
            'total': qs.count(),
            'highRisk': qs.filter(risk_level__in=['critical', 'high']).count(),
            'mediumRisk': qs.filter(risk_level='medium').count(),
            'todayNew': qs.filter(analysis_timestamp__gte=_today_start_utc()).count(),
        }
        return Response(stats)


class ReportListView(APIView):
    """报告列表：分页 + risk_level / attack_type / keyword 过滤。

    keyword 走 MySQL LIKE（D11），匹配 attack_type_ai / ip / path。
    """

    def get(self, request):
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 10))
        risk_level = request.query_params.get('risk_level', None)
        attack_type = request.query_params.get('attack_type', None)
        keyword = request.query_params.get('keyword', None)

        qs = AnalysisReport.objects.all()

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

        total = qs.count()
        reports = []
        for report in qs.order_by('-analysis_timestamp')[(page - 1) * size: page * size]:
            reports.append({
                'id': report.event_id,
                'title': f"检测到{report.attack_type_ai or '未知攻击'}",
                'riskLevel': (report.risk_level or 'unknown').lower(),
                'attackType': report.attack_type_ai or '未知攻击',
                'sourceIp': report.ip or '未知IP',
                'targetPath': report.path or '未知路径',
                'generatedAt': _format_local(report.analysis_timestamp),
                'aiConfidence': report.risk_score or 0,
                'status': 'pending',
            })

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
        try:
            report = AnalysisReport.objects.get(event_id=report_id)
        except AnalysisReport.DoesNotExist:
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
        })
