import random
import time
from datetime import datetime, timedelta

ATTACK_IPS = [
    "39.144.100.52",
    "185.199.108.10",
    "45.83.12.9",
    "103.25.88.17",
    "203.55.81.44"
]

NORMAL_UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
]

ATTACK_UA = [
    "sqlmap/1.8.0#stable (http://sqlmap.org)",
    "curl/7.68.0",
    "python-requests/2.31.0",
    "Wget/1.21.4 (linux-gnu)",
    "Go-http-client/2.0"
]

NORMAL_STATUS = ["200", "304"]
ATTACK_STATUS = ["200", "401", "403", "404", "500"]

NORMAL_URLS = [
    "/",
    "/index.html",
    "/products",
    "/about",
    "/profile",
    "/cart",
    "/contact",
    "/login",
    "/images/logo.png",
    "/css/main.css",
    "/js/app.js"
]

SQL_INJECTION_TEMPLATES = [
    "/login?username=admin' OR '1'='1",
    "/products?id=1 UNION SELECT",
    "/search?q=' OR 1=1--",
    "/api/user?id=1' OR 'a'='a",
    "/login?password=' OR '1'='1",
    "/products?id=0'; DROP TABLE users--",
    "/search?q=test' AND 1=1",
    "/api/item?id=1' AND SLEEP(5)--",
    "/login?username=admin'--",
    "/products?id=1' OR 1=1--"
]

COMMAND_INJECTION_TEMPLATES = [
    "/api/ping?host=127.0.0.1;whoami",
    "/cgi-bin/test.cgi?cmd=id",
    "/run?cmd=cat+/etc/passwd",
    "/api/exec?cmd=ls+-la",
    "/cgi-bin/script.cgi?host=127.0.0.1;cat+/etc/shadow",
    "/api/system?command=uname+-a",
    "/run?cmd=netstat+-an",
    "/cgi-bin/test.cgi?cmd=ps+aux",
    "/api/ping?host=127.0.0.1;cat+/var/log/auth.log",
    "/exec?cmd=rm+-rf+/"
]

SENSITIVE_ACCESS_TEMPLATES = [
    "/.env",
    "/.git/config",
    "/config.php",
    "/backup.sql",
    "/database.sql",
    "/admin/config.php",
    "/wp-config.php",
    "/.htaccess",
    "/server-status",
    "/info.php"
]

DIRECTORY_SCAN_TEMPLATES = [
    "/admin",
    "/phpmyadmin",
    "/manager/html",
    "/.git",
    "/admin/login",
    "/admin/panel",
    "/wp-admin",
    "/uploads",
    "/backup",
    "/test"
]

PATH_TRAVERSAL_TEMPLATES = [
    "/../../../../etc/passwd",
    "/download?file=../../../../windows/win.ini",
    "/../etc/passwd",
    "/download?file=../../../etc/shadow",
    "/../../etc/passwd",
    "/file?path=../../../../etc/hosts",
    "/../config.php",
    "/download?file=../../../../var/log/apache2/access.log",
    "/../../windows/system32/config/sam",
    "/../.env"
]

XSS_TEMPLATES = [
    "/search?q=<script>alert(1)</script>",
    "/comment?msg=<img src=x onerror=alert(1)>",
    "/search?q=%3Cscript%3Ealert(1)%3C/script%3E",
    "/post?content=<svg/onload=alert(1)>",
    "/comment?msg=<iframe src=javascript:alert(1)>",
    "/search?q=<body onload=alert(1)>",
    "/message?text=%3Cscript%3Eprompt(1)%3C/script%3E",
    "/post?content=<img src=x onerror=confirm(1)>",
    "/comment?msg=<script>document.cookie</script>",
    "/search?q=<script>window.location.href='http://evil.com'</script>"
]

BRUTE_FORCE_USERS = ["admin", "root", "test"]
BRUTE_FORCE_PASSWORDS = ["123456", "admin123", "password"]


def generate_normal_ip():
    return f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"


def format_nginx_log(ip, timestamp, method, url, status, size, referer, ua):
    return f'{ip} - - [{timestamp}] "{method} {url} HTTP/1.1" {status} {size} "{referer}" "{ua}"'


def generate_normal_log(current_time):
    ip = generate_normal_ip()
    ua = random.choice(NORMAL_UA)
    url = random.choice(NORMAL_URLS)
    status = random.choice(NORMAL_STATUS)
    size = random.randint(100, 2000)
    referer = "-" if random.random() > 0.3 else f"http://example.com{random.choice(NORMAL_URLS)}"
    
    method = "GET"
    if url == "/login":
        method = random.choice(["GET", "POST"])
    
    timestamp = current_time.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return format_nginx_log(ip, timestamp, method, url, status, size, referer, ua)


def generate_sql_injection(current_time):
    ip = random.choice(ATTACK_IPS)
    ua = random.choice(ATTACK_UA)
    url = random.choice(SQL_INJECTION_TEMPLATES)
    status = random.choice(ATTACK_STATUS)
    size = random.randint(50, 500)
    referer = "-"
    
    timestamp = current_time.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return format_nginx_log(ip, timestamp, "GET", url, status, size, referer, ua)


def generate_xss(current_time):
    ip = random.choice(ATTACK_IPS)
    ua = random.choice(ATTACK_UA)
    url = random.choice(XSS_TEMPLATES)
    status = random.choice(ATTACK_STATUS)
    size = random.randint(50, 800)
    referer = "-"
    
    timestamp = current_time.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return format_nginx_log(ip, timestamp, "GET", url, status, size, referer, ua)


def generate_command_injection(current_time):
    ip = random.choice(ATTACK_IPS)
    ua = random.choice(ATTACK_UA)
    url = random.choice(COMMAND_INJECTION_TEMPLATES)
    status = random.choice(ATTACK_STATUS)
    size = random.randint(50, 1000)
    referer = "-"
    
    timestamp = current_time.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return format_nginx_log(ip, timestamp, "GET", url, status, size, referer, ua)


def generate_sensitive_access(current_time):
    ip = random.choice(ATTACK_IPS)
    ua = random.choice(ATTACK_UA)
    url = random.choice(SENSITIVE_ACCESS_TEMPLATES)
    status = random.choice(ATTACK_STATUS)
    size = random.randint(0, 1000)
    referer = "-"
    
    timestamp = current_time.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return format_nginx_log(ip, timestamp, "GET", url, status, size, referer, ua)


def generate_directory_scan(current_time):
    ip = random.choice(ATTACK_IPS)
    ua = random.choice(ATTACK_UA)
    url = random.choice(DIRECTORY_SCAN_TEMPLATES)
    status = random.choice(ATTACK_STATUS)
    size = random.randint(0, 500)
    referer = "-"
    
    timestamp = current_time.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return format_nginx_log(ip, timestamp, "GET", url, status, size, referer, ua)


def generate_path_traversal(current_time):
    ip = random.choice(ATTACK_IPS)
    ua = random.choice(ATTACK_UA)
    url = random.choice(PATH_TRAVERSAL_TEMPLATES)
    status = random.choice(ATTACK_STATUS)
    size = random.randint(0, 500)
    referer = "-"
    
    timestamp = current_time.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return format_nginx_log(ip, timestamp, "GET", url, status, size, referer, ua)


def generate_brute_force(current_time):
    ip = random.choice(ATTACK_IPS)
    ua = random.choice(ATTACK_UA)
    url = "/login"
    status = random.choice(["401", "403", "200"])
    size = random.randint(100, 500)
    referer = "-"
    
    timestamp = current_time.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return format_nginx_log(ip, timestamp, "POST", url, status, size, referer, ua)


def main():
    random.seed(42)
    
    total_logs = 1000
    normal_count = int(total_logs * 0.6)
    attack_count = total_logs - normal_count
    
    attack_types = [
        generate_sql_injection,
        generate_xss,
        generate_command_injection,
        generate_sensitive_access,
        generate_directory_scan,
        generate_path_traversal,
        generate_brute_force
    ]
    
    current_time = datetime(2026, 6, 27, 8, 0, 0)
    
    logs = []
    
    for _ in range(normal_count):
        logs.append(generate_normal_log(current_time))
        current_time += timedelta(seconds=random.randint(1, 5))
    
    for _ in range(attack_count):
        attack_func = random.choice(attack_types)
        logs.append(attack_func(current_time))
        current_time += timedelta(seconds=random.randint(1, 5))
    
    output_path = "demo_access.log"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(logs))
    
    print(f"生成数量: {len(logs)} 条")
    print(f"输出路径: {output_path}")
    print("完成提示: demo_access.log 已成功生成")


if __name__ == "__main__":
    main()