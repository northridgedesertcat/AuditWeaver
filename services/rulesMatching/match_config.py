# 规则匹配配置文件 - 检测规则相关配置

# 导入外部关键词文件
from keywords.sql_injection import SQL_INJECTION_KEYWORDS, SQL_INJECTION_PATTERNS
from keywords.xss import XSS_KEYWORDS, XSS_PATTERNS
from keywords.command_injection import COMMAND_INJECTION_KEYWORDS, COMMAND_INJECTION_PATTERNS
from keywords.path_traversal import PATH_TRAVERSAL_KEYWORDS, PATH_TRAVERSAL_PATTERNS
from keywords.csrf import CSRF_KEYWORDS, CSRF_PATTERNS
from keywords.bot import BOT_KEYWORDS, BOT_PATTERNS
from keywords.sensitive_access import SENSITIVE_ACCESS_KEYWORDS, SENSITIVE_ACCESS_PATTERNS

# 攻击类型定义
ATTACK_TYPES = {
    'SQL_INJECTION': 'sql_injection',
    'XSS': 'xss',
    'COMMAND_INJECTION': 'command_injection',
    'PATH_TRAVERSAL': 'path_traversal',
    'CSRF': 'csrf',
    'BOT': 'bot',
    'DDoS': 'ddos',
    'SENSITIVE_ACCESS': 'sensitive_access'
}

# SQL注入检测规则
SQL_INJECTION_RULES = {
    'keywords': SQL_INJECTION_KEYWORDS,
    'patterns': SQL_INJECTION_PATTERNS,
    'threshold': 1
}

# XSS检测规则
XSS_RULES = {
    'keywords': XSS_KEYWORDS,
    'patterns': XSS_PATTERNS,
    'threshold': 1
}

# 命令注入检测规则
COMMAND_INJECTION_RULES = {
    'keywords': COMMAND_INJECTION_KEYWORDS,
    'patterns': COMMAND_INJECTION_PATTERNS,
    'threshold': 1
}

# 路径遍历检测规则
PATH_TRAVERSAL_RULES = {
    'keywords': PATH_TRAVERSAL_KEYWORDS,
    'patterns': PATH_TRAVERSAL_PATTERNS,
    'threshold': 1
}

# CSRF检测规则
CSRF_RULES = {
    'keywords': CSRF_KEYWORDS,
    'patterns': CSRF_PATTERNS,
    'threshold': 1
}

# Bot检测规则
BOT_RULES = {
    'keywords': BOT_KEYWORDS,
    'patterns': BOT_PATTERNS,
    'threshold': 1
}

# DDoS检测规则
DDOS_RULES = {
    'rate_threshold': 100,  # 每分钟请求数阈值
    'ip_block_threshold': 500  # 每小时请求数阈值
}

# 敏感访问检测规则
SENSITIVE_ACCESS_RULES = {
    'keywords': SENSITIVE_ACCESS_KEYWORDS,
    'patterns': SENSITIVE_ACCESS_PATTERNS,
    'threshold': 1
}

# 规则配置映射
RULES_CONFIG = {
    ATTACK_TYPES['SQL_INJECTION']: SQL_INJECTION_RULES,
    ATTACK_TYPES['XSS']: XSS_RULES,
    ATTACK_TYPES['COMMAND_INJECTION']: COMMAND_INJECTION_RULES,
    ATTACK_TYPES['PATH_TRAVERSAL']: PATH_TRAVERSAL_RULES,
    ATTACK_TYPES['CSRF']: CSRF_RULES,
    ATTACK_TYPES['BOT']: BOT_RULES,
    ATTACK_TYPES['SENSITIVE_ACCESS']: SENSITIVE_ACCESS_RULES
}

# 日志字段映射
LOG_FIELDS = {
    'ip': 'ip',
    'timestamp': 'timestamp',
    'method': 'method',
    'path': 'path',
    'http_version': 'http_version',
    'status': 'status',
    'bytes': 'bytes',
    'referrer': 'referrer',
    'user_agent': 'user_agent'
}

# 检测配置
DETECTION_CONFIG = {
    'max_matches': 5,  # 每个日志最多检测出的攻击类型数
    'min_confidence': 0.1,  # 最小置信度
    'log_file': 'd:\\tools\\ProgrammeTools\\python\\正规项目\\LogSentinel\\services\\rulesMatching\\detections.log'  # 检测结果日志文件
}