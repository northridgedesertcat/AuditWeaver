# 敏感访问关键词配置

# 敏感访问关键词
SENSITIVE_ACCESS_KEYWORDS = [
    'admin', 'login', 'signin', 'auth',
    'password', 'passwd', 'secret', 'token',
    'api', 'rest', 'webservice', 'xmlrpc',
    '.git', '.svn', '.hg', 'backup',
    'config', 'settings', 'database'
]

# 敏感访问正则模式
SENSITIVE_ACCESS_PATTERNS = [
    r'\badmin\b',
    r'\blogin\b',
    r'\bsignin\b',
    r'\bauth\b',
    r'\bpassword\b',
    r'\bpasswd\b',
    r'\bsecret\b',
    r'\btoken\b',
    r'\bapi\b',
    r'\b\.git\b',
    r'\b\.svn\b',
    r'\bbackup\b',
    r'\bconfig\b'
]
