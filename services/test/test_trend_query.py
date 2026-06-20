from elasticsearch import Elasticsearch
from datetime import datetime, timedelta

es = Elasticsearch('http://localhost:19200', basic_auth=('elastic', 'password'))

# 测试 ES 连接
print(f"ES 可用: {es.ping()}")

# 模拟后端的查询逻辑
now = datetime.utcnow()
start_time = now - timedelta(hours=24)

print(f"当前时间 (UTC): {now}")
print(f"开始时间 (UTC): {start_time}")

# 修复：不使用 format 参数，或者使用正确的 extended_bounds 格式
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
                "fixed_interval": "1h",
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

print(f"\n聚合结果数量: {len(buckets)}")

# 找出有数据的桶
non_zero_buckets = [b for b in buckets if b['doc_count'] > 0]
print(f"\n有数据的桶数量: {len(non_zero_buckets)}")
for bucket in non_zero_buckets:
    print(f"  {bucket['key_as_string']}: {bucket['doc_count']}")

# 显示最后几个桶
print("\n最后5个桶:")
for bucket in buckets[-5:]:
    print(f"  {bucket['key_as_string']}: {bucket['doc_count']}")

# 检查数据的时间范围
print("\n检查数据时间范围:")
result2 = es.search(index="nginx-log-raw", body={
    "query": {
        "range": {
            "@timestamp": {
                "gte": start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "lte": now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }
        }
    },
    "size": 10,
    "sort": [{"@timestamp": {"order": "desc"}}]
})

print(f"匹配的数据数量: {len(result2['hits']['hits'])}")
for hit in result2['hits']['hits']:
    print(f"  时间: {hit['_source'].get('@timestamp')}")