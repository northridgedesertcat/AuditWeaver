from elasticsearch import Elasticsearch
from datetime import datetime

es = Elasticsearch('http://localhost:19200', basic_auth=('elastic', 'password'))

print("=== 检查 nginx-log-raw 索引数据 ===")

# 获取最近一条数据的时间
result = es.search(index='nginx-log-raw', body={
    "size": 1,
    "sort": [{"@timestamp": {"order": "desc"}}]
})

if result['hits']['hits']:
    latest_doc = result['hits']['hits'][0]['_source']
    print(f"最新数据时间: {latest_doc.get('@timestamp')}")
else:
    print("索引中没有数据")

# 获取最早一条数据的时间
result2 = es.search(index='nginx-log-raw', body={
    "size": 1,
    "sort": [{"@timestamp": {"order": "asc"}}]
})

if result2['hits']['hits']:
    earliest_doc = result2['hits']['hits'][0]['_source']
    print(f"最早数据时间: {earliest_doc.get('@timestamp')}")

# 统计数据总数
count = es.count(index='nginx-log-raw')
print(f"总数据量: {count['count']}")

# 查看今天的数据量
now = datetime.utcnow()
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
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
today_count = es.count(index='nginx-log-raw', body=today_query)
print(f"今日数据量: {today_count['count']}")

# 查看过去24小时的数据量
from datetime import timedelta
start_time = now - timedelta(hours=24)
query_24h = {
    "query": {
        "range": {
            "@timestamp": {
                "gte": start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "lte": now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }
        }
    }
}
count_24h = es.count(index='nginx-log-raw', body=query_24h)
print(f"过去24小时数据量: {count_24h['count']}")

# 查看所有数据的时间分布
histogram = es.search(index='nginx-log-raw', body={
    "size": 0,
    "aggs": {
        "daily": {
            "date_histogram": {
                "field": "@timestamp",
                "interval": "day",
                "format": "yyyy-MM-dd"
            }
        }
    }
})

print("\n按日期统计:")
for bucket in histogram['aggregations']['daily']['buckets']:
    print(f"  {bucket['key_as_string']}: {bucket['doc_count']} 条")