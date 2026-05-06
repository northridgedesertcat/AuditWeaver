# CSRF检测关键词和模式

CSRF_KEYWORDS = [
    'csrf',
    'token',
    'nonce',
    'form',
    'post',
    'get',
    'cookie',
    'session'
]

CSRF_PATTERNS = [
    r'\bcsrf\b',
    r'\btoken\b',
    r'\bnonce\b'
]
