from elasticsearch import Elasticsearch
from datetime import datetime

es = Elasticsearch('http://localhost:19200', basic_auth=('elastic', 'password'))

now = datetime.utcnow()
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

print(f"当前时间: {now}")
print(f"今天开始时间: {today_start}")

# 查询今日日志
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

result_today = es.count(index="nginx-log-raw", body=today_query)
print(f"\n今日日志数: {result_today['count']}")

# 查询总日志数
result_all = es.count(index="nginx-log-raw")
print(f"总日志数: {result_all['count']}")

# 查看最近的日志时间
result = es.search(index="nginx-log-raw", body={"query": {"match_all": {}}, "sort": [{"@timestamp": {"order": "desc"}}], "size": 1})
if result['hits']['hits']:
    latest = result['hits']['hits'][0]['_source']
    print(f"\n最新日志时间: {latest.get('@timestamp', 'N/A')}")
