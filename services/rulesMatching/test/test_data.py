# 测试数据文件

def load_test_logs():
    """加载测试日志"""
    return [
        # 正常日志
        {
            'ip': '192.168.1.1',
            'timestamp': '16/Apr/2026:10:00:00 +0000',
            'method': 'GET',
            'path': '/index.html',
            'http_version': 'HTTP/1.1',
            'status': 200,
            'bytes': 1024,
            'referrer': '-',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        },
        # SQL注入攻击
        {
            'ip': '10.0.0.1',
            'timestamp': '16/Apr/2026:10:01:00 +0000',
            'method': 'GET',
            'path': "/login.php?username=admin' OR 1=1 --&password=test",
            'http_version': 'HTTP/1.1',
            'status': 200,
            'bytes': 512,
            'referrer': '-',
            'user_agent': 'Mozilla/5.0'
        },
        # XSS攻击
        {
            'ip': '10.0.0.2',
            'timestamp': '16/Apr/2026:10:02:00 +0000',
            'method': 'POST',
            'path': '/comment.php',
            'http_version': 'HTTP/1.1',
            'status': 200,
            'bytes': 256,
            'referrer': 'http://example.com',
            'user_agent': 'Mozilla/5.0',
            'body': '<script>alert("XSS")</script>'
        },
        # 命令注入攻击
        {
            'ip': '10.0.0.3',
            'timestamp': '16/Apr/2026:10:03:00 +0000',
            'method': 'GET',
            'path': '/ping.php?ip=127.0.0.1; cat /etc/passwd',
            'http_version': 'HTTP/1.1',
            'status': 200,
            'bytes': 1024,
            'referrer': '-',
            'user_agent': 'Mozilla/5.0'
        },
        # 路径遍历攻击
        {
            'ip': '10.0.0.4',
            'timestamp': '16/Apr/2026:10:04:00 +0000',
            'method': 'GET',
            'path': '/download.php?file=../../etc/passwd',
            'http_version': 'HTTP/1.1',
            'status': 200,
            'bytes': 512,
            'referrer': '-',
            'user_agent': 'Mozilla/5.0'
        },
        # Bot访问
        {
            'ip': '10.0.0.5',
            'timestamp': '16/Apr/2026:10:05:00 +0000',
            'method': 'GET',
            'path': '/sitemap.xml',
            'http_version': 'HTTP/1.1',
            'status': 200,
            'bytes': 2048,
            'referrer': '-',
            'user_agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
        },
        # 敏感访问
        {
            'ip': '10.0.0.6',
            'timestamp': '16/Apr/2026:10:06:00 +0000',
            'method': 'GET',
            'path': '/admin/login.php',
            'http_version': 'HTTP/1.1',
            'status': 200,
            'bytes': 1024,
            'referrer': '-',
            'user_agent': 'Mozilla/5.0'
        }
    ]
