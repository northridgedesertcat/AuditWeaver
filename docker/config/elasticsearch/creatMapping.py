#!/usr/bin/env python
"""创建 Elasticsearch 索引 Mapping 脚本

根据项目中三个模块的数据结构创建正确的索引 mapping:
1. nginx-log-raw - Logstash 输出的原始日志
2. matched_logs - rulesMatching 模块输出的攻击日志
3. log_analysis_reports - agent 模块输出的AI分析报告
"""

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError
import sys

def get_es_client(host='localhost', port=19200, user='elastic', password='password'):
    """获取 Elasticsearch 客户端"""
    try:
        es = Elasticsearch(
            hosts=[f"http://{host}:{port}"],
            basic_auth=(user, password),
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        if es.ping():
            print(f"✅ 成功连接到 Elasticsearch: http://{host}:{port}")
            return es
        else:
            print(f"❌ 无法连接到 Elasticsearch: http://{host}:{port}")
            return None
    except Exception as e:
        print(f"❌ Elasticsearch 连接失败: {str(e)}")
        return None

def create_index(es, index_name, mapping, force_recreate=False):
    """创建索引"""
    try:
        if es.indices.exists(index=index_name):
            if force_recreate:
                print(f"⚠️ 索引 {index_name} 已存在，正在删除并重新创建...")
                es.indices.delete(index=index_name)
            else:
                print(f"ℹ️ 索引 {index_name} 已存在，跳过创建")
                return False
        
        es.indices.create(index=index_name, body=mapping)
        print(f"✅ 成功创建索引: {index_name}")
        return True
    except RequestError as e:
        print(f"❌ 创建索引 {index_name} 失败: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ 创建索引 {index_name} 异常: {str(e)}")
        return False

def get_nginx_log_raw_mapping():
    """nginx-log-raw 索引 mapping
    
    数据来源: Logstash pipeline (logstash.conf)
    字段说明:
    - @timestamp: Logstash 解析的时间戳 (ISO8601)
    - event_id: UUID，由 Logstash uuid 过滤器生成
    - ip: 客户端IP地址
    - method: HTTP方法
    - path: 请求路径
    - http_version: HTTP版本
    - status: HTTP状态码
    - bytes: 响应字节数
    - referrer: 来源页
    - user_agent: 用户代理
    - log_source: 日志来源 (nginx)
    - audit_user: 审计用户 (同ip)
    - audit_event: 审计事件 (method + path)
    - pipeline: 流水线状态
    """
    return {
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date", "format": "strict_date_optional_time||yyyy-MM-dd HH:mm:ss"},
                "@version": {"type": "keyword"},
                "bytes": {"type": "long"},
                "event": {
                    "properties": {
                        "original": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 1024}}}
                    }
                },
                "event_id": {"type": "keyword"},
                "http_version": {"type": "keyword"},
                "ip": {"type": "ip"},
                "method": {"type": "keyword"},
                "path": {"type": "keyword"},
                "referrer": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
                "status": {"type": "integer"},
                "user_agent": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
                "log_source": {"type": "keyword"},
                "audit_user": {"type": "keyword"},
                "audit_event": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 512}}},
                "pipeline": {
                    "properties": {
                        "rule_matching": {
                            "properties": {
                                "status": {"type": "keyword"}
                            }
                        },
                        "agent_analysis": {
                            "properties": {
                                "status": {"type": "keyword"}
                            }
                        }
                    }
                }
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "default": {"type": "standard"}
                }
            }
        }
    }

def get_matched_logs_mapping():
    """matched_logs 索引 mapping
    
    数据来源: rulesMatching 模块 (data_saver.py)
    字段说明:
    - 继承 nginx-log-raw 的所有字段
    - rule_match: 规则匹配结果
    - ingestion_time: 写入时间
    - pipeline: 更新后的流水线状态
    """
    return {
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date", "format": "strict_date_optional_time||yyyy-MM-dd HH:mm:ss"},
                "@version": {"type": "keyword"},
                "event": {
                    "properties": {
                        "original": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 1024}}}
                    }
                },
                "event_id": {"type": "keyword"},
                "ip": {"type": "ip"},
                "method": {"type": "keyword"},
                "path": {"type": "keyword"},
                "http_version": {"type": "keyword"},
                "status": {"type": "integer"},
                "bytes": {"type": "long"},
                "referrer": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
                "user_agent": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
                "log_source": {"type": "keyword"},
                "audit_user": {"type": "keyword"},
                "audit_event": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 512}}},
                
                "rule_match": {
                    "properties": {
                        "is_matched": {"type": "boolean"},
                        "rule_id": {"type": "keyword"},
                        "matched_type": {"type": "keyword"},
                        "confidence": {"type": "float"},
                        "severity": {"type": "keyword"},
                        "matched_items": {"type": "object"}
                    }
                },
                
                "ingestion_time": {"type": "date", "format": "strict_date_optional_time||yyyy-MM-dd HH:mm:ss"},
                
                "pipeline": {
                    "properties": {
                        "rule_matching": {
                            "properties": {
                                "status": {"type": "keyword"}
                            }
                        },
                        "agent_analysis": {
                            "properties": {
                                "status": {"type": "keyword"}
                            }
                        }
                    }
                }
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "default": {"type": "standard"}
                }
            }
        }
    }

def get_log_analysis_reports_mapping():
    """log_analysis_reports 索引 mapping
    
    数据来源: agent 模块 (elastic_mapping_config.py)
    字段说明:
    - 原始日志字段 (event_id, ip, path, method, status, user_agent)
    - 规则匹配结果 (attack_type, confidence, severity)
    - AI分析结果 (risk_level, risk_score, attack_type_ai, summary, reasoning, recommendations)
    - 时间戳字段使用 epoch_millis 格式
    - dify_response 和 original_log 不参与搜索
    """
    return {
        "mappings": {
            "properties": {
                "event_id": {"type": "keyword"},
                "ip": {"type": "ip"},
                "path": {"type": "keyword"},
                "method": {"type": "keyword"},
                "status": {"type": "integer"},
                "user_agent": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
                
                "attack_type": {"type": "keyword"},
                "confidence": {"type": "float"},
                "severity": {"type": "keyword"},
                
                "risk_level": {"type": "keyword"},
                "risk_score": {"type": "integer"},
                "attack_type_ai": {"type": "keyword"},
                "summary": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 512}}},
                
                "reasoning": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                },
                
                "recommendations": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                },
                
                "log_timestamp": {"type": "date", "format": "epoch_millis"},
                "analysis_timestamp": {"type": "date", "format": "epoch_millis"},
                "ingestion_time": {"type": "date", "format": "epoch_millis"},
                
                "dify_response": {"type": "object", "enabled": False},
                "original_log": {"type": "object", "enabled": False}
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "default": {"type": "standard"}
                }
            }
        }
    }

def main():
    print("=" * 70)
    print("创建 Elasticsearch 索引 Mapping")
    print("=" * 70)
    
    import argparse
    parser = argparse.ArgumentParser(description='创建 Elasticsearch 索引 Mapping')
    parser.add_argument('--host', default='localhost', help='Elasticsearch 主机')
    parser.add_argument('--port', type=int, default=19200, help='Elasticsearch 端口')
    parser.add_argument('--user', default='elastic', help='Elasticsearch 用户名')
    parser.add_argument('--password', default='password', help='Elasticsearch 密码')
    parser.add_argument('--force', action='store_true', help='强制重新创建索引')
    args = parser.parse_args()
    
    es = get_es_client(args.host, args.port, args.user, args.password)
    if not es:
        print("❌ 无法连接到 Elasticsearch，退出")
        sys.exit(1)
    
    print("\n--- 创建索引 ---")
    
    indices = [
        ("nginx-log-raw", get_nginx_log_raw_mapping()),
        ("matched_logs", get_matched_logs_mapping()),
        ("log_analysis_reports", get_log_analysis_reports_mapping()),
    ]
    
    success_count = 0
    for index_name, mapping in indices:
        print(f"\n处理索引: {index_name}")
        if create_index(es, index_name, mapping, args.force):
            success_count += 1
    
    print(f"\n{'=' * 70}")
    print(f"创建完成: {success_count}/{len(indices)} 个索引")
    print(f"{'=' * 70}")
    
    es.close()

if __name__ == "__main__":
    main()