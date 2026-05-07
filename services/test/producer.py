from kafka import KafkaProducer
import time
from datetime import datetime, timezone
import random

producer = KafkaProducer(
    bootstrap_servers='localhost:29092'
)

# 模拟 IP 地址池
ip_pool = ['39.144.100.52', '192.168.1.101', '10.0.0.5', '172.16.0.3']

# 模拟 User-Agent 池
user_agents = [
    "Mozilla/5.0",
    "curl/7.68.0",
    "Python-urllib/3.11",
    "Googlebot/2.1 (+http://www.google.com/bot.html)"
]

# 可能的攻击 URL
attack_urls = [
    "/login?username=admin' OR '1'='1&password=123",
    "/search?q=<script>alert(1)</script>",
    "/api/data?filter=../../etc/passwd"
]

# 正常 URL
normal_urls = [
    "/index",
    "/about",
    "/products?id=23",
    "/contact"
]

# 异常爬虫行为 URL
bot_urls = [
    "/robots.txt",
    "/sitemap.xml",
    "/api/data?id=999999",
    "/login?redirect=/admin"
]

def generate_log():
    now = datetime.now(timezone.utc)
    timestamp_str = now.strftime('%d/%b/%Y:%H:%M:%S %z')

    ip = random.choice(ip_pool)
    user_agent = random.choice(user_agents)

    # 随机选择日志类型
    log_type = random.choices(
        ['normal', 'attack', 'bot'],
        weights=[0.6, 0.2, 0.2],  # 60% normal, 20% attack, 20% bot
        k=1
    )[0]

    if log_type == 'normal':
        url = random.choice(normal_urls)
        status = random.choices([200, 301], weights=[0.9, 0.1])[0]
        size = random.randint(500, 2500)
    elif log_type == 'attack':
        url = random.choice(attack_urls)
        status = random.choices([200, 403, 500], weights=[0.6, 0.3, 0.1])[0]
        size = random.randint(200, 1000)
    else:  # bot/异常行为
        url = random.choice(bot_urls)
        status = random.choices([200, 404, 429], weights=[0.5, 0.3, 0.2])[0]
        size = random.randint(100, 1500)

    log = f'{ip} - - [{timestamp_str}] "GET {url} HTTP/1.1" {status} {size} "-" "{user_agent}"'
    return log

while True:
    log = generate_log()
    producer.send('your-topic', log.encode('utf-8'))
    print("sent:", log)
    time.sleep(2)