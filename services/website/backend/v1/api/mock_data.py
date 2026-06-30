import time

_now = int(time.time() * 1000)

MOCK_ALERTS = [
    {
        "id": "alert-001",
        "title": "SQL 注入攻击检测",
        "description": "检测到来自 185.234.12.45 的 SQL 注入攻击尝试",
        "severity": "critical",
        "status": "active",
        "source": "Web Application Firewall",
        "timestamp": _now - 1000 * 60 * 30,
        "count": 12,
    },
    {
        "id": "alert-002",
        "title": "异常登录行为",
        "description": "用户 admin_zhang 从异常地点登录",
        "severity": "high",
        "status": "active",
        "source": "Authentication Service",
        "timestamp": _now - 1000 * 60 * 35,
        "count": 1,
    },
    {
        "id": "alert-003",
        "title": "端口扫描活动",
        "description": "检测到内部 IP 10.0.1.45 进行大规模端口扫描",
        "severity": "high",
        "status": "investigating",
        "source": "Network IDS",
        "timestamp": _now - 1000 * 60 * 50,
        "count": 1024,
    },
    {
        "id": "alert-004",
        "title": "SSL 证书即将过期",
        "description": "生产环境 SSL 证书将在 15 天后过期",
        "severity": "medium",
        "status": "active",
        "source": "Certificate Monitor",
        "timestamp": _now - 1000 * 60 * 60 * 6,
        "count": 1,
    },
    {
        "id": "alert-005",
        "title": "API 速率限制超出",
        "description": "API 密钥 ak_prod_xxx 超出速率限制",
        "severity": "low",
        "status": "resolved",
        "source": "API Gateway",
        "timestamp": _now - 1000 * 60 * 60 * 6.5,
        "count": 15000,
    },
    {
        "id": "alert-006",
        "title": "磁盘空间警告",
        "description": "服务器 db-primary 磁盘使用率达到 85%",
        "severity": "medium",
        "status": "active",
        "source": "Infrastructure Monitor",
        "timestamp": _now - 1000 * 60 * 60 * 8,
        "count": 1,
    },
    {
        "id": "alert-007",
        "title": "可疑文件上传",
        "description": "检测到可能包含恶意代码的文件上传",
        "severity": "high",
        "status": "resolved",
        "source": "Antivirus Scanner",
        "timestamp": _now - 1000 * 60 * 60 * 16,
        "count": 3,
    },
    {
        "id": "alert-008",
        "title": "数据库连接池耗尽",
        "description": "应用服务器连接池使用率达到 95%",
        "severity": "medium",
        "status": "resolved",
        "source": "Database Monitor",
        "timestamp": _now - 1000 * 60 * 60 * 19,
        "count": 1,
    },
]

MOCK_ALERT_RULES = [
    {"id": 1, "name": "SQL 注入检测", "enabled": True, "severity": "critical", "notifications": True},
    {"id": 2, "name": "暴力破解检测", "enabled": True, "severity": "high", "notifications": True},
    {"id": 3, "name": "异常登录检测", "enabled": True, "severity": "high", "notifications": True},
    {"id": 4, "name": "端口扫描检测", "enabled": True, "severity": "medium", "notifications": False},
    {"id": 5, "name": "SSL 证书监控", "enabled": True, "severity": "medium", "notifications": True},
    {"id": 6, "name": "磁盘空间监控", "enabled": False, "severity": "low", "notifications": False},
]

MOCK_INCIDENTS = [
    {
        "id": "INC-2024-001",
        "title": "疑似 APT 攻击事件",
        "description": "检测到高级持续性威胁攻击特征，多个系统受到影响",
        "severity": "critical",
        "status": "investigating",
        "assignee": "张安全",
        "createdAt": _now - 1000 * 60 * 60 * 5,
        "updatedAt": _now - 1000 * 60 * 30,
        "progress": 45,
        "affectedSystems": ["web-server-01", "db-primary", "api-gateway"],
        "timeline": [
            {"time": _now - 1000 * 60 * 60 * 5, "action": "事件创建", "user": "AI 系统"},
            {"time": _now - 1000 * 60 * 60 * 4.5, "action": "分配给 张安全", "user": "系统管理员"},
            {"time": _now - 1000 * 60 * 60 * 4, "action": "开始调查", "user": "张安全"},
            {"time": _now - 1000 * 60 * 60 * 1.5, "action": "隔离受影响系统", "user": "张安全"},
            {"time": _now - 1000 * 60 * 30, "action": "更新调查进展", "user": "张安全"},
        ],
    },
    {
        "id": "INC-2024-002",
        "title": "数据泄露调查",
        "description": "发现敏感数据可能被未授权访问",
        "severity": "high",
        "status": "in_progress",
        "assignee": "李响应",
        "createdAt": _now - 1000 * 60 * 60 * 23,
        "updatedAt": _now - 1000 * 60 * 60 * 6,
        "progress": 70,
        "affectedSystems": ["db-replica-02", "backup-server"],
        "timeline": [
            {"time": _now - 1000 * 60 * 60 * 23, "action": "事件创建", "user": "DLP 系统"},
            {"time": _now - 1000 * 60 * 60 * 22.5, "action": "分配给 李响应", "user": "值班经理"},
            {"time": _now - 1000 * 60 * 60 * 21, "action": "确认数据范围", "user": "李响应"},
            {"time": _now - 1000 * 60 * 60 * 6, "action": "通知相关部门", "user": "李响应"},
        ],
    },
    {
        "id": "INC-2024-003",
        "title": "DDoS 攻击事件",
        "description": "遭受大规模分布式拒绝服务攻击",
        "severity": "high",
        "status": "resolved",
        "assignee": "王防护",
        "createdAt": _now - 1000 * 60 * 60 * 53,
        "updatedAt": _now - 1000 * 60 * 60 * 49,
        "progress": 100,
        "affectedSystems": ["load-balancer", "cdn-edge"],
        "timeline": [
            {"time": _now - 1000 * 60 * 60 * 53, "action": "攻击检测", "user": "WAF 系统"},
            {"time": _now - 1000 * 60 * 60 * 52.5, "action": "启动应急响应", "user": "王防护"},
            {"time": _now - 1000 * 60 * 60 * 52, "action": "启用 DDoS 防护", "user": "王防护"},
            {"time": _now - 1000 * 60 * 60 * 50, "action": "攻击流量下降", "user": "系统"},
            {"time": _now - 1000 * 60 * 60 * 49, "action": "事件关闭", "user": "王防护"},
        ],
    },
    {
        "id": "INC-2024-004",
        "title": "内部威胁调查",
        "description": "员工账户异常行为需要调查",
        "severity": "medium",
        "status": "pending",
        "assignee": None,
        "createdAt": _now - 1000 * 60 * 60 * 2,
        "updatedAt": _now - 1000 * 60 * 60 * 2,
        "progress": 0,
        "affectedSystems": ["hr-system"],
        "timeline": [
            {"time": _now - 1000 * 60 * 60 * 2, "action": "事件创建", "user": "UEBA 系统"},
        ],
    },
]

MOCK_ANOMALIES = [
    {
        "id": "anom-001",
        "type": "login_anomaly",
        "title": "异常登录行为",
        "description": "用户 admin_zhang 从未知 IP 地址登录，与历史行为模式不符",
        "severity": "high",
        "score": 92,
        "timestamp": _now - 1000 * 60 * 30,
        "source": "Authentication Service",
        "details": {
            "user": "admin_zhang",
            "ip": "185.234.12.45",
            "location": "俄罗斯, 莫斯科",
            "normalLocation": "中国, 北京",
        },
        "status": "open",
    },
    {
        "id": "anom-002",
        "type": "data_exfiltration",
        "title": "大量数据导出",
        "description": "检测到异常大量数据查询和导出操作",
        "severity": "critical",
        "score": 98,
        "timestamp": _now - 1000 * 60 * 35,
        "source": "Database Monitor",
        "details": {
            "user": "service_account_01",
            "dataVolume": "2.3GB",
            "normalVolume": "50MB",
            "tables": ["users", "transactions", "sensitive_data"],
            "duration": "15 分钟",
        },
        "status": "investigating",
    },
    {
        "id": "anom-003",
        "type": "network_scan",
        "title": "内部端口扫描",
        "description": "检测到来自内部 IP 的大规模端口扫描活动",
        "severity": "medium",
        "score": 75,
        "timestamp": _now - 1000 * 60 * 50,
        "source": "Network IDS",
        "details": {
            "sourceIp": "10.0.1.45",
            "scannedPorts": 1024,
            "targetRange": "10.0.0.0/16",
            "duration": "5 分钟",
        },
        "status": "open",
    },
    {
        "id": "anom-004",
        "type": "privilege_escalation",
        "title": "权限提升尝试",
        "description": "检测到可能的权限提升攻击尝试",
        "severity": "high",
        "score": 88,
        "timestamp": _now - 1000 * 60 * 60 * 1.5,
        "source": "HIDS",
        "details": {
            "user": "developer_li",
            "action": "sudo 权限请求",
            "command": "sudo cat /etc/shadow",
            "server": "prod-web-01",
        },
        "status": "resolved",
    },
    {
        "id": "anom-005",
        "type": "api_abuse",
        "title": "API 滥用",
        "description": "检测到 API 调用频率异常升高",
        "severity": "low",
        "score": 62,
        "timestamp": _now - 1000 * 60 * 60 * 2,
        "source": "API Gateway",
        "details": {
            "apiKey": "ak_prod_xxx",
            "requests": 15000,
            "normalRequests": 1000,
            "endpoint": "/api/v1/users",
            "period": "1 小时",
        },
        "status": "open",
    },
]

MOCK_SERVERS = [
    {"id": "srv-001", "name": "web-server-01", "type": "Web Server", "status": "healthy", "cpu": 45, "memory": 62, "disk": 38, "network": "1.2 Gbps", "uptime": "45 天", "location": "北京 DC1"},
    {"id": "srv-002", "name": "web-server-02", "type": "Web Server", "status": "healthy", "cpu": 52, "memory": 58, "disk": 42, "network": "980 Mbps", "uptime": "45 天", "location": "北京 DC1"},
    {"id": "srv-003", "name": "api-gateway", "type": "API Gateway", "status": "warning", "cpu": 89, "memory": 78, "disk": 55, "network": "2.5 Gbps", "uptime": "30 天", "location": "北京 DC2"},
    {"id": "srv-004", "name": "db-primary", "type": "Database", "status": "healthy", "cpu": 35, "memory": 72, "disk": 85, "network": "500 Mbps", "uptime": "90 天", "location": "上海 DC1"},
    {"id": "srv-005", "name": "db-replica", "type": "Database", "status": "healthy", "cpu": 28, "memory": 65, "disk": 82, "network": "450 Mbps", "uptime": "90 天", "location": "上海 DC1"},
    {"id": "srv-006", "name": "cache-server", "type": "Cache", "status": "healthy", "cpu": 22, "memory": 45, "disk": 15, "network": "800 Mbps", "uptime": "60 天", "location": "北京 DC1"},
    {"id": "srv-007", "name": "log-collector", "type": "Log Server", "status": "healthy", "cpu": 55, "memory": 68, "disk": 72, "network": "1.5 Gbps", "uptime": "45 天", "location": "北京 DC2"},
    {"id": "srv-008", "name": "backup-server", "type": "Backup", "status": "error", "cpu": 5, "memory": 12, "disk": 95, "network": "50 Mbps", "uptime": "0 天", "location": "深圳 DC1"},
]

MOCK_THREATS = [
    {
        "id": "threat-001",
        "indicator": "185.234.12.45",
        "type": "IP 地址",
        "category": "C2 服务器",
        "severity": "critical",
        "source": "AlienVault OTX",
        "firstSeen": _now - 1000 * 60 * 60 * 5,
        "lastSeen": _now - 1000 * 60 * 30,
        "country": "俄罗斯",
        "tags": ["APT", "恶意软件"],
    },
    {
        "id": "threat-002",
        "indicator": "malware.evil-domain.com",
        "type": "域名",
        "category": "恶意软件分发",
        "severity": "high",
        "source": "VirusTotal",
        "firstSeen": _now - 1000 * 60 * 60 * 30,
        "lastSeen": _now - 1000 * 60 * 60 * 3,
        "country": "乌克兰",
        "tags": ["恶意软件", "下载器"],
    },
    {
        "id": "threat-003",
        "indicator": "phishing-bank-login.com",
        "type": "域名",
        "category": "钓鱼网站",
        "severity": "high",
        "source": "PhishTank",
        "firstSeen": _now - 1000 * 60 * 60 * 9,
        "lastSeen": _now - 1000 * 60 * 60 * 1,
        "country": "美国",
        "tags": ["钓鱼", "金融"],
    },
    {
        "id": "threat-004",
        "indicator": "d41d8cd98f00b204e9800998ecf8427e",
        "type": "文件哈希",
        "category": "勒索软件",
        "severity": "critical",
        "source": "VirusTotal",
        "firstSeen": _now - 1000 * 60 * 60 * 53,
        "lastSeen": _now - 1000 * 60 * 60 * 7,
        "country": "未知",
        "tags": ["勒索软件", "加密"],
    },
    {
        "id": "threat-005",
        "indicator": "10.0.0.45",
        "type": "IP 地址",
        "category": "内部威胁",
        "severity": "medium",
        "source": "内部威胁情报",
        "firstSeen": _now - 1000 * 60 * 60 * 2,
        "lastSeen": _now - 1000 * 60 * 60 * 1,
        "country": "内部网络",
        "tags": ["端口扫描", "侦察"],
    },
]

MOCK_AI_MODELS = [
    {"id": "model-001", "name": "威胁检测模型 v3.2", "type": "分类模型", "status": "running", "accuracy": 95.3, "latency": "45ms", "lastTrained": _now - 1000 * 60 * 60 * 24, "tasksProcessed": 12847},
    {"id": "model-002", "name": "异常行为分析器", "type": "异常检测", "status": "running", "accuracy": 92.8, "latency": "78ms", "lastTrained": _now - 1000 * 60 * 60 * 48, "tasksProcessed": 8956},
    {"id": "model-003", "name": "用户行为画像", "type": "聚类模型", "status": "training", "accuracy": 89.5, "latency": "120ms", "lastTrained": _now - 1000 * 60 * 60 * 72, "tasksProcessed": 5623},
    {"id": "model-004", "name": "日志模式识别", "type": "序列模型", "status": "running", "accuracy": 94.1, "latency": "35ms", "lastTrained": _now - 1000 * 60 * 60 * 24, "tasksProcessed": 23456},
]

MOCK_RECENT_ANALYSES = [
    {"id": 1, "type": "威胁检测", "input": "可疑 SQL 注入请求", "result": "高风险攻击", "confidence": 96.5, "status": "completed", "time": _now - 1000 * 60 * 2},
    {"id": 2, "type": "行为分析", "input": "用户 admin 异常登录模式", "result": "账户可能被盗", "confidence": 88.2, "status": "completed", "time": _now - 1000 * 60 * 5},
    {"id": 3, "type": "异常检测", "input": "服务器流量模式", "result": "DDoS 攻击前兆", "confidence": 75.8, "status": "completed", "time": _now - 1000 * 60 * 8},
    {"id": 4, "type": "模式识别", "input": "防火墙日志批量分析", "result": "处理中...", "confidence": 0, "status": "processing", "time": _now},
    {"id": 5, "type": "风险评估", "input": "新部署服务安全评估", "result": "中等风险", "confidence": 82.3, "status": "completed", "time": _now - 1000 * 60 * 15},
]

MOCK_THREAT_FEEDS = [
    {"id": "feed-001", "name": "AlienVault OTX", "type": "开源情报", "status": "active", "lastUpdate": _now - 1000 * 60 * 5, "indicators": 125847},
    {"id": "feed-002", "name": "VirusTotal", "type": "恶意软件", "status": "active", "lastUpdate": _now - 1000 * 60 * 10, "indicators": 89456},
    {"id": "feed-003", "name": "AbuseIPDB", "type": "恶意 IP", "status": "active", "lastUpdate": _now - 1000 * 60 * 15, "indicators": 456789},
    {"id": "feed-004", "name": "PhishTank", "type": "钓鱼网站", "status": "active", "lastUpdate": _now - 1000 * 60 * 30, "indicators": 34567},
    {"id": "feed-005", "name": "内部威胁情报", "type": "自定义", "status": "active", "lastUpdate": _now - 1000 * 60 * 60, "indicators": 1234},
]

DASHBOARD_STATS = {
    "logVolume": "2.3M",
    "attackLogs": 28,
    "highSeverityAlerts": 174,
    "riskIps": 12,
    "totalLogs": 1847,
    "avgResponseTime": "1.2s",
}

ALERT_STATS = {
    "total": 8,
    "critical": 1,
    "high": 3,
    "active": 4,
}

INCIDENT_STATS = {
    "total": 47,
    "open": 12,
    "investigating": 5,
    "resolved": 30,
    "avgResponseTime": "23分钟",
    "avgResolutionTime": "4.2小时",
}

ANOMALY_STATS = {
    "active": 12,
    "today": 47,
    "avgScore": 76.5,
    "avgResponseTime": "18分钟",
}

INFRA_STATS = {
    "totalServers": 8,
    "healthyServers": 6,
    "warningServers": 1,
    "errorServers": 1,
    "avgCpu": 42,
    "avgMemory": 58,
}

THREAT_STATS = {
    "totalIndicators": 707893,
    "newToday": 1234,
    "matchedAlerts": 47,
    "activeFeeds": 5,
    "criticalThreats": 12,
    "highThreats": 28,
}

AI_STATS = {
    "activeModels": 4,
    "todayAnalyses": 3470,
    "avgAccuracy": 94.2,
    "avgLatency": "52ms",
}