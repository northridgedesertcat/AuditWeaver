from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    AlertSerializer,
    AlertRuleSerializer,
    IncidentSerializer,
    AnomalySerializer,
    ServerSerializer,
    ThreatSerializer,
    AIModelSerializer,
    DashboardStatsSerializer,
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
    DASHBOARD_STATS,
    ALERT_STATS,
    INCIDENT_STATS,
    ANOMALY_STATS,
    INFRA_STATS,
    THREAT_STATS,
    AI_STATS,
)
from .es_client import is_es_available, get_es_client
from datetime import datetime, timedelta, timezone

class HealthCheckView(APIView):
    def get(self, request):
        es_available = is_es_available()
        return Response({
            "status": "ok",
            "elasticsearch": "available" if es_available else "unavailable"
        })

class ThreatDistributionView(APIView):
    """威胁等级分布接口

    从 Elasticsearch 的 log_analysis_reports 索引中聚合 risk_level 字段。
    数据来源: dify_response.data.outputs.structured_output.risk_level
    在 agent 写入时已通过 extract_dify_fields 扁平化到顶级 risk_level 字段。

    支持五种风险等级: Critical / High / Medium / Low / Informational
    """
    def get(self, request):
        # 全部五种风险等级（包含 Informational）
        all_levels = ['Critical', 'High', 'Medium', 'Low', 'Informational']
        level_color_map = {
            'Critical': 'oklch(0.5 0.25 25)',      # 严重 - 红色
            'High': 'oklch(0.65 0.2 60)',           # 高危 - 橙色
            'Medium': 'oklch(0.75 0.15 95)',        # 中危 - 黄色
            'Low': 'oklch(0.75 0.12 145)',          # 低危 - 绿色
            'Informational': 'oklch(0.7 0.15 230)'  # 信息 - 蓝色
        }
        level_label_map = {
            'Critical': '严重',
            'High': '高危',
            'Medium': '中危',
            'Low': '低危',
            'Informational': '信息'
        }

        # 默认全 0 的返回结构
        distribution = {
            level: {
                'name': level_label_map[level],
                'value': 0,
                'color': level_color_map[level]
            }
            for level in all_levels
        }

        # 是否限定时间范围（默认查询全部）
        time_range = request.query_params.get('range', 'all')

        if is_es_available():
            try:
                es = get_es_client()
                if es:
                    # 构建查询条件
                    must_clauses = []
                    if time_range == 'today':
                        today_start = datetime.utcnow().replace(
                            hour=0, minute=0, second=0, microsecond=0
                        )
                        # log_analysis_reports 使用毫秒时间戳
                        today_start_ms = int(today_start.timestamp() * 1000)
                        now_ms = int(datetime.utcnow().timestamp() * 1000)
                        must_clauses.append({
                            "range": {
                                "analysis_timestamp": {
                                    "gte": today_start_ms,
                                    "lte": now_ms
                                }
                            }
                        })

                    query = {"match_all": {}} if not must_clauses else {
                        "bool": {"must": must_clauses}
                    }

                    agg_body = {
                        "size": 0,
                        "query": query,
                        "aggs": {
                            "risk_levels": {
                                "terms": {
                                    "field": "risk_level.keyword",
                                    "size": 10
                                }
                            }
                        }
                    }

                    result = es.search(index="log_analysis_reports", body=agg_body)
                    buckets = result.get('aggregations', {}).get('risk_levels', {}).get('buckets', [])
                    
                    # 调试日志
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"ThreatDistribution ES buckets: {buckets}")

                    for bucket in buckets:
                        level = bucket['key']
                        count = bucket['doc_count']
                        # 支持大小写不敏感匹配
                        if level:
                            level_lower = level.lower()
                            level_mapping = {
                                'critical': 'Critical',
                                'high': 'High',
                                'medium': 'Medium',
                                'low': 'Low',
                                'informational': 'Informational',
                                'unknown': 'Low'
                            }
                            level_key = level_mapping.get(level_lower, level.capitalize())
                            if level_key in distribution:
                                distribution[level_key]['value'] = count

                    total = sum(item['value'] for item in distribution.values())
                    return Response({
                        'data': distribution,
                        'total': total,
                        'range': time_range
                    })
            except Exception as e:
                pass

        # ES 不可用时也返回 0 数据结构
        total = sum(item['value'] for item in distribution.values())
        return Response({
            'data': distribution,
            'total': total,
            'range': time_range
        })


class DashboardStatsView(APIView):
    def get(self, request):
        stats = {
            "logVolume": "0",
            "attackLogs": 0,
            "highSeverityAlerts": 0,
            "riskIps": 0,
            "totalLogs": 0,
            "avgResponseTime": "0ms",
        }
        
        if is_es_available():
            try:
                es = get_es_client()
                if es:
                    now = datetime.utcnow()
                    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    # nginx-log-raw 使用 ISO8601 格式
                    today_start_str = today_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    now_str = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    # log_analysis_reports 使用毫秒时间戳
                    today_start_ms = int(today_start.timestamp() * 1000)
                    now_ms = int(now.timestamp() * 1000)
                    
                    # 1. 今日日志量 - nginx-log-raw (ISO8601 格式)
                    nginx_today_query = {
                        "query": {
                            "range": {
                                "@timestamp": {
                                    "gte": today_start_str,
                                    "lte": now_str
                                }
                            }
                        }
                    }
                    nginx_result = es.count(index="nginx-log-raw", body=nginx_today_query)
                    today_count = nginx_result.get('count', 0)
                    
                    if today_count >= 1000000:
                        stats['logVolume'] = f"{today_count/1000000:.1f}M"
                    elif today_count >= 1000:
                        stats['logVolume'] = f"{today_count//1000}K"
                    else:
                        stats['logVolume'] = str(today_count)
                    
                    # 2. 总日志数 - nginx-log-raw
                    total_result = es.count(index="nginx-log-raw")
                    stats['totalLogs'] = total_result.get('count', 0)
                    
                    # 3. 今日攻击日志数 - log_analysis_reports (毫秒时间戳)
                    attack_today_query = {
                        "query": {
                            "range": {
                                "analysis_timestamp": {
                                    "gte": today_start_ms,
                                    "lte": now_ms
                                }
                            }
                        }
                    }
                    attack_result = es.count(index="log_analysis_reports", body=attack_today_query)
                    stats['attackLogs'] = attack_result.get('count', 0)
                    
                    # 4. 今日高危告警数 - log_analysis_reports (毫秒时间戳)
                    high_severity_query = {
                        "query": {
                            "bool": {
                                "must": [
                                    {
                                        "range": {
                                            "analysis_timestamp": {
                                                "gte": today_start_ms,
                                                "lte": now_ms
                                            }
                                        }
                                    },
                                    {
                                        "terms": {
                                            "risk_level": ["Critical", "High"]
                                        }
                                    }
                                ]
                            }
                        }
                    }
                    high_severity_result = es.count(index="log_analysis_reports", body=high_severity_query)
                    stats['highSeverityAlerts'] = high_severity_result.get('count', 0)
                    
            except Exception as e:
                pass
        
        serializer = DashboardStatsSerializer(stats)
        return Response(serializer.data)

class LogsView(APIView):
    def get(self, request):
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 20))
        ip = request.query_params.get('ip', None)
        method = request.query_params.get('method', None)
        status = request.query_params.get('status', None)
        path = request.query_params.get('path', None)
        
        if is_es_available():
            try:
                es = get_es_client()
                if es:
                    query = {
                        "query": {
                            "bool": {
                                "must": []
                            }
                        },
                        "sort": [{"@timestamp": {"order": "desc"}}],
                        "from": (page - 1) * size,
                        "size": size
                    }
                    
                    if ip:
                        query['query']['bool']['must'].append({"match": {"ip": ip}})
                    if method:
                        query['query']['bool']['must'].append({"match": {"method": method}})
                    if status:
                        query['query']['bool']['must'].append({"match": {"status": status}})
                    if path:
                        query['query']['bool']['must'].append({"wildcard": {"path": f"*{path}*"}})
                    
                    result = es.search(index="nginx-log-raw", body=query)
                    logs = [hit['_source'] for hit in result['hits']['hits']]
                    total = result['hits']['total']['value']
                    
                    return Response({
                        "data": logs,
                        "total": total,
                        "page": page,
                        "size": size
                    })
            except Exception as e:
                pass
        
        return Response({
            "data": [],
            "total": 0,
            "page": page,
            "size": size
        })

class LogStatsView(APIView):
    def get(self, request):
        stats = {
            "total": 0,
            "today": 0,
            "top_ips": [],
            "top_paths": [],
            "status_distribution": {}
        }
        
        if is_es_available():
            try:
                es = get_es_client()
                if es:
                    now = datetime.utcnow()
                    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    
                    total_result = es.count(index="nginx-log-raw")
                    stats['total'] = total_result.get('count', 0)
                    
                    today_query = {
                        "query": {
                            "range": {
                                "@timestamp": {
                                    "gte": today_start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                                    "lte": now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                                }
                            }
                        }
                    }
                    today_result = es.count(index="nginx-log-raw", body=today_query)
                    stats['today'] = today_result.get('count', 0)
                    
                    ip_agg = {
                        "size": 0,
                        "aggs": {
                            "top_ips": {
                                "terms": {"field": "ip", "size": 10}
                            }
                        }
                    }
                    ip_result = es.search(index="nginx-log-raw", body=ip_agg)
                    stats['top_ips'] = [
                        {"ip": bucket['key'], "count": bucket['doc_count']}
                        for bucket in ip_result['aggregations']['top_ips']['buckets']
                    ]
                    
                    path_agg = {
                        "size": 0,
                        "aggs": {
                            "top_paths": {
                                "terms": {"field": "path", "size": 10}
                            }
                        }
                    }
                    path_result = es.search(index="nginx-log-raw", body=path_agg)
                    stats['top_paths'] = [
                        {"path": bucket['key'], "count": bucket['doc_count']}
                        for bucket in path_result['aggregations']['top_paths']['buckets']
                    ]
                    
                    status_agg = {
                        "size": 0,
                        "aggs": {
                            "status_dist": {
                                "terms": {"field": "status", "size": 20}
                            }
                        }
                    }
                    status_result = es.search(index="nginx-log-raw", body=status_agg)
                    stats['status_distribution'] = {
                        str(bucket['key']): bucket['doc_count']
                        for bucket in status_result['aggregations']['status_dist']['buckets']
                    }
            except Exception as e:
                pass
        
        return Response(stats)

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

class RecentAlertsView(APIView):
    """最近告警接口
    
    从 Elasticsearch 的 log_analysis_reports 索引中查询最近的告警记录。
    只返回最近10条记录。
    
    字段映射:
    - severity: risk_level
    - message: "检测到可疑" + attack_type_ai
    - ip: original_log.ip
    - time: ingestion_time
    """
    def get(self, request):
        alerts = []
        
        if is_es_available():
            try:
                es = get_es_client()
                if es:
                    query = {
                        "size": 10,
                        "query": {
                            "match_all": {}
                        },
                        "sort": [{"ingestion_time": {"order": "desc"}}]
                    }
                    
                    result = es.search(index="log_analysis_reports", body=query)
                    hits = result.get('hits', {}).get('hits', [])
                    
                    for hit in hits:
                        source = hit.get('_source', {})
                        risk_level = source.get('risk_level', 'Low')
                        attack_type = source.get('attack_type_ai', '未知攻击')
                        original_log = source.get('original_log', {})
                        ip = original_log.get('ip', '未知IP')
                        ingestion_time = source.get('ingestion_time', '')
                        
                        alert = {
                            "id": hit.get('_id', ''),
                            "severity": risk_level.lower(),
                            "message": f"检测到可疑{attack_type}",
                            "source": "AI Security Analyzer",
                            "time": self.format_time(ingestion_time),
                            "ip": ip
                        }
                        alerts.append(alert)
            except Exception as e:
                pass
        
        return Response({"data": alerts})
    
    def format_time(self, timestamp):
        if not timestamp:
            return "未知时间"
        
        try:
            from datetime import datetime, timezone, timedelta
            
            if isinstance(timestamp, str):
                if timestamp.endswith('Z'):
                    timestamp = timestamp[:-1] + '+00:00'
                dt = datetime.fromisoformat(timestamp)
            else:
                dt = datetime.fromtimestamp(timestamp / 1000)
            
            now = datetime.now(timezone.utc)
            diff = now - dt.replace(tzinfo=timezone.utc)
            
            if diff.days > 0:
                return f"{diff.days} 天前"
            elif diff.seconds >= 3600:
                hours = diff.seconds // 3600
                return f"{hours} 小时前"
            elif diff.seconds >= 60:
                minutes = diff.seconds // 60
                return f"{minutes} 分钟前"
            else:
                return "刚刚"
        except:
            return "未知时间"

class LogTrendView(APIView):
    def get(self, request):
        trend_data = []
        
        if is_es_available():
            try:
                es = get_es_client()
                if es:
                    now = datetime.utcnow()
                    start_time = now - timedelta(hours=24)
                    # nginx-log-raw 使用 ISO8601 格式
                    start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    now_str = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    
                    query = {
                        "size": 0,
                        "query": {
                            "range": {
                                "@timestamp": {
                                    "gte": start_time_str,
                                    "lte": now_str
                                }
                            }
                        },
                        "aggs": {
                            "hourly": {
                                "date_histogram": {
                                    "field": "@timestamp",
                                    "calendar_interval": "hour",
                                    "min_doc_count": 0,
                                    "extended_bounds": {
                                        "min": start_time_str,
                                        "max": now_str
                                    }
                                }
                            }
                        }
                    }
                    
                    result = es.search(index="nginx-log-raw", body=query)
                    buckets = result['aggregations']['hourly']['buckets']
                    
                    trend_data = []
                    china_tz = timezone(timedelta(hours=8))
                    for bucket in buckets:
                        key_str = bucket['key_as_string']
                        if 'T' in key_str:
                            utc_dt = datetime.fromisoformat(key_str.replace('Z', '+00:00'))
                            china_dt = utc_dt.astimezone(china_tz)
                            time_part = china_dt.strftime("%H:%M")
                        else:
                            time_part = key_str
                        trend_data.append({
                            "time": time_part,
                            "logs": bucket['doc_count']
                        })
            except Exception as e:
                pass
        
        if not trend_data:
            trend_data = []
            now_utc = datetime.now(timezone.utc)
            china_tz = timezone(timedelta(hours=8))
            now_china = now_utc.astimezone(china_tz)
            for i in range(24):
                hour_time = now_china - timedelta(hours=23 - i)
                trend_data.append({
                    "time": hour_time.strftime("%H:%M"),
                    "logs": 0
                })
        
        return Response({"data": trend_data})

class ReportStatsView(APIView):
    """报告统计数据接口
    
    从 Elasticsearch 的 log_analysis_reports 索引中聚合报告统计数据。
    
    返回数据:
    - total: log_analysis_reports 总数
    - highRisk: risk_level 为 Critical 或 High 的数量
    - mediumRisk: risk_level 为 Medium 的数量
    - todayNew: analysis_timestamp 为今天的数量
    """
    def get(self, request):
        import logging
        logger = logging.getLogger(__name__)
        
        stats = {
            "total": 0,
            "highRisk": 0,
            "mediumRisk": 0,
            "todayNew": 0,
        }
        
        logger.info(f"ReportStatsView: is_es_available() = {is_es_available()}")
        
        if is_es_available():
            try:
                es = get_es_client()
                logger.info(f"ReportStatsView: es client = {es}")
                
                if es:
                    # 检查索引是否存在
                    try:
                        indices = es.cat.indices(index="log_analysis_reports", format="json")
                        logger.info(f"ReportStatsView: indices = {indices}")
                    except Exception as idx_err:
                        logger.error(f"ReportStatsView: indices check error = {idx_err}")
                    
                    # 1. 总报告数 - 使用 search 获取总数
                    total_search = {
                        "size": 0,
                        "track_total_hits": True
                    }
                    total_result = es.search(index="log_analysis_reports", body=total_search)
                    stats['total'] = total_result['hits']['total']['value']
                    logger.info(f"ReportStatsView: total = {stats['total']}")
                    
                    # 2. 高危报告数 (Critical + High)
                    high_risk_search = {
                        "size": 0,
                        "track_total_hits": True,
                        "query": {
                            "terms": {
                                "risk_level": ["Critical", "High"]
                            }
                        }
                    }
                    high_result = es.search(index="log_analysis_reports", body=high_risk_search)
                    stats['highRisk'] = high_result['hits']['total']['value']
                    logger.info(f"ReportStatsView: highRisk = {stats['highRisk']}")
                    
                    # 3. 中危报告数 (Medium)
                    medium_risk_search = {
                        "size": 0,
                        "track_total_hits": True,
                        "query": {
                            "match": {
                                "risk_level": "Medium"
                            }
                        }
                    }
                    medium_result = es.search(index="log_analysis_reports", body=medium_risk_search)
                    stats['mediumRisk'] = medium_result['hits']['total']['value']
                    logger.info(f"ReportStatsView: mediumRisk = {stats['mediumRisk']}")
                    
                    # 4. 今日新增
                    now = datetime.utcnow()
                    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    today_start_ms = int(today_start.timestamp() * 1000)
                    now_ms = int(now.timestamp() * 1000)
                    
                    today_search = {
                        "size": 0,
                        "track_total_hits": True,
                        "query": {
                            "range": {
                                "analysis_timestamp": {
                                    "gte": today_start_ms,
                                    "lte": now_ms
                                }
                            }
                        }
                    }
                    today_result = es.search(index="log_analysis_reports", body=today_search)
                    stats['todayNew'] = today_result['hits']['total']['value']
                    logger.info(f"ReportStatsView: todayNew = {stats['todayNew']}")
                    
            except Exception as e:
                logger.error(f"ReportStatsView error: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        
        return Response(stats)

class ReportDetailView(APIView):
    """报告详情接口
    
    从 Elasticsearch 的 log_analysis_reports 索引中获取报告详情。
    
    字段映射:
    - id: ES文档ID
    - title: 根据 attack_type_ai 生成的标题
    - riskLevel: risk_level（转换为小写）
    - attackType: attack_type_ai
    - confidence: confidence（转换为百分比）
    - riskScore: risk_score
    - generatedAt: analysis_timestamp
    - summary: summary（分析总结）
    - reasoning: reasoning（原因分析，数组）
    - recommendations: recommendations（处置建议，数组）
    - originalRiskData: 原始风险数据（包含event_id, ip, log_timestamp, user_agent, status, path, original_log）
    """
    def get(self, request, report_id):
        report = None
        
        if is_es_available():
            try:
                es = get_es_client()
                if es:
                    result = es.get(index="log_analysis_reports", id=report_id)
                    source = result.get('_source', {})
                    
                    # 获取字段值
                    attack_type_ai = source.get('attack_type_ai', source.get('attack_type', '未知攻击'))
                    risk_level_raw = source.get('risk_level', 'Low')
                    confidence = source.get('confidence', 0)
                    risk_score = source.get('risk_score', 0)
                    analysis_timestamp = source.get('analysis_timestamp', '')
                    summary = source.get('summary', '')
                    reasoning = source.get('reasoning', [])
                    recommendations = source.get('recommendations', [])
                    
                    # 获取event_id
                    original_log = source.get('original_log', {})
                    event_id = source.get('event_id', original_log.get('event_id', ''))
                    
                    # 查询原始日志
                    original_log_content = ""
                    if event_id:
                        try:
                            log_query = {
                                "query": {
                                    "match": {
                                        "event_id": event_id
                                    }
                                },
                                "size": 1
                            }
                            log_result = es.search(index="nginx-log-raw", body=log_query)
                            if log_result['hits']['hits']:
                                log_source = log_result['hits']['hits'][0]['_source']
                                original_log_content = log_source.get('event', {}).get('original', '')
                        except Exception:
                            pass
                    
                    # 原始风险数据
                    original_risk_data = {
                        "event_id": event_id,
                        "ip": source.get('ip', original_log.get('ip', '')),
                        "log_timestamp": self.format_timestamp(source.get('log_timestamp', original_log.get('@timestamp', ''))),
                        "user_agent": source.get('user_agent', original_log.get('user_agent', '')),
                        "status": source.get('status', original_log.get('status', 0)),
                        "path": source.get('path', original_log.get('path', '')),
                        "original_log": original_log_content
                    }
                    
                    # 转换风险等级为小写
                    risk_level_lower = risk_level_raw.lower() if risk_level_raw else 'low'
                    
                    # 构建标题
                    title = f"检测到{attack_type_ai}"
                    
                    # 格式化时间
                    formatted_time = self.format_timestamp(analysis_timestamp)
                    
                    # 转换置信度为百分比
                    confidence_percent = int(confidence * 100) if isinstance(confidence, (int, float)) else int(confidence)
                    
                    report = {
                        "id": report_id,
                        "title": title,
                        "riskLevel": risk_level_lower,
                        "attackType": attack_type_ai,
                        "confidence": confidence_percent,
                        "riskScore": risk_score,
                        "generatedAt": formatted_time,
                        "summary": summary,
                        "reasoning": reasoning,
                        "recommendations": recommendations,
                        "originalRiskData": original_risk_data
                    }
                    
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"ReportDetailView error: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        
        if report:
            return Response(report)
        return Response({"error": "Report not found"}, status=status.HTTP_404_NOT_FOUND)
    
    def format_timestamp(self, timestamp):
        """格式化时间戳（UTC转本地时间）"""
        if not timestamp:
            return "未知时间"
        
        try:
            from datetime import datetime, timezone
            
            if isinstance(timestamp, str):
                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        dt = datetime.strptime(timestamp.replace('+00:00', 'Z').rstrip('Z'), fmt.replace('Z', '').replace('+00:00', ''))
                        # 如果没有时区信息，假设是 UTC
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        # 转换为本地时间
                        local_dt = dt.astimezone()
                        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        continue
                return timestamp
            elif isinstance(timestamp, (int, float)):
                # UTC 时间戳转为本地时间
                dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                local_dt = dt.astimezone()
                return local_dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                return str(timestamp)
        except:
            return str(timestamp)

class ReportListView(APIView):
    """报告列表接口
    
    从 Elasticsearch 的 log_analysis_reports 索引中获取报告列表。
    
    字段映射:
    - id: ES文档ID
    - title: 根据 attack_type_ai 生成的标题
    - riskLevel: risk_level
    - attackType: attack_type_ai
    - sourceIp: original_log.ip 或 ip
    - targetPath: original_log.path 或 path
    - generatedAt: analysis_timestamp
    - aiConfidence: confidence
    - status: 默认 "pending"
    """
    def get(self, request):
        reports = []
        total = 0
        
        # 获取分页参数
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 10))
        
        # 获取筛选参数
        risk_level = request.query_params.get('risk_level', None)
        attack_type = request.query_params.get('attack_type', None)
        keyword = request.query_params.get('keyword', None)
        
        if is_es_available():
            try:
                es = get_es_client()
                if es:
                    # 构建查询
                    must_clauses = []
                    
                    if risk_level and risk_level != 'all':
                        must_clauses.append({
                            "match": {
                                "risk_level": risk_level.capitalize() if risk_level in ['critical', 'high', 'medium', 'low'] else risk_level
                            }
                        })
                    
                    if attack_type and attack_type != 'all':
                        must_clauses.append({
                            "match": {
                                "attack_type_ai": attack_type
                            }
                        })
                    
                    if keyword:
                        must_clauses.append({
                            "multi_match": {
                                "query": keyword,
                                "fields": ["attack_type_ai", "original_log.ip", "original_log.path"]
                            }
                        })
                    
                    query = {
                        "query": {
                            "bool": {
                                "must": must_clauses if must_clauses else [{"match_all": {}}]
                            }
                        },
                        "sort": [{"analysis_timestamp": {"order": "desc"}}],
                        "from": (page - 1) * size,
                        "size": size,
                        "track_total_hits": True
                    }
                    
                    result = es.search(index="log_analysis_reports", body=query)
                    hits = result.get('hits', {}).get('hits', [])
                    total = result['hits']['total']['value']
                    
                    for hit in hits:
                        source = hit.get('_source', {})
                        original_log = source.get('original_log', {})
                        
                        # 获取字段值
                        attack_type_ai = source.get('attack_type_ai', '未知攻击')
                        risk_level_raw = source.get('risk_level', 'Low')
                        ip = original_log.get('ip', source.get('ip', '未知IP'))
                        path = original_log.get('path', source.get('path', '未知路径'))
                        analysis_timestamp = source.get('analysis_timestamp', '')
                        confidence = source.get('confidence', 0)
                        
                        # 转换风险等级为小写
                        risk_level_lower = risk_level_raw.lower() if risk_level_raw else 'low'
                        
                        # 构建标题
                        title = f"检测到{attack_type_ai}"
                        
                        # 格式化时间
                        formatted_time = self.format_timestamp(analysis_timestamp)
                        
                        # 转换置信度为百分比
                        confidence_percent = int(confidence * 100) if isinstance(confidence, (int, float)) else int(confidence)
                        
                        report = {
                            "id": hit.get('_id', ''),
                            "title": title,
                            "riskLevel": risk_level_lower,
                            "attackType": attack_type_ai,
                            "sourceIp": ip,
                            "targetPath": path,
                            "generatedAt": formatted_time,
                            "aiConfidence": confidence_percent,
                            "status": "pending"  # 默认状态
                        }
                        reports.append(report)
                        
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"ReportListView error: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        
        return Response({
            "data": reports,
            "total": total,
            "page": page,
            "size": size
        })
    
    def format_timestamp(self, timestamp):
        """格式化时间戳（UTC转本地时间）"""
        if not timestamp:
            return "未知时间"
        
        try:
            from datetime import datetime, timezone
            
            # 处理不同格式的时间戳
            if isinstance(timestamp, str):
                # 尝试多种格式
                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        dt = datetime.strptime(timestamp.replace('+00:00', 'Z').rstrip('Z'), fmt.replace('Z', '').replace('+00:00', ''))
                        # 如果没有时区信息，假设是 UTC
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        # 转换为本地时间
                        local_dt = dt.astimezone()
                        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        continue
                return timestamp
            elif isinstance(timestamp, (int, float)):
                # UTC 时间戳转为本地时间
                dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                local_dt = dt.astimezone()
                return local_dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                return str(timestamp)
        except:
            return str(timestamp)