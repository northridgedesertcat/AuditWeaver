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
                        today_start_str = today_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                        now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
                        must_clauses.append({
                            "range": {
                                "analysis_timestamp": {
                                    "gte": today_start_str,
                                    "lte": now_str
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
                                    "field": "risk_level",
                                    "size": 10,
                                    # 包含全部五种等级
                                    "include": all_levels
                                }
                            }
                        }
                    }

                    result = es.search(index="log_analysis_reports", body=agg_body)
                    buckets = result.get('aggregations', {}).get('risk_levels', {}).get('buckets', [])

                    for bucket in buckets:
                        level = bucket['key']
                        count = bucket['doc_count']
                        if level in distribution:
                            distribution[level]['value'] = count

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
                    today_start_str = today_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    now_str = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    
                    # 1. 今日日志量 - nginx-log-raw
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
                    
                    # 3. 今日攻击日志数 - log_analysis_reports
                    today_date = today_start.strftime("%Y-%m-%d")
                    attack_today_query = {
                        "query": {
                            "match": {
                                "analysis_timestamp": today_date
                            }
                        }
                    }
                    attack_result = es.count(index="log_analysis_reports", body=attack_today_query)
                    stats['attackLogs'] = attack_result.get('count', 0)
                    
                    # 4. 今日高危告警数 - log_analysis_reports, risk_level 为 Critical 或 High
                    high_severity_query = {
                        "query": {
                            "bool": {
                                "must": [
                                    {
                                        "match": {
                                            "analysis_timestamp": today_date
                                        }
                                    },
                                    {
                                        "terms": {
                                            "dify_response.data.outputs.structured_output.risk_level.keyword": ["Critical", "High"]
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
                    
                    query = {
                        "size": 0,
                        "query": {
                            "range": {
                                "@timestamp": {
                                    "gte": start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                                    "lte": now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
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
                                        "min": start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                                        "max": now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
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