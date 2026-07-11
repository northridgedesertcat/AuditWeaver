# XSS关键词配置

# XSS关键词
XSS_KEYWORDS = [
    '<script>', '</script>', '<iframe>', '</iframe>',
    'javascript:', 'onerror=', 'onload=', 'onclick=',
    'eval(', 'alert(', 'prompt(', 'confirm(',
    '<img', 'src=', 'href=', 'data:'
]

# XSS正则模式
XSS_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'<iframe[^>]*>.*?</iframe>',
    r'javascript:\s*[^\s]+',
    r'on\w+\s*=\s*["].*?["]',
    r'eval\s*\(.*?\)',
    r'alert\s*\(.*?\)',
    r'prompt\s*\(.*?\)',
    r'confirm\s*\(.*?\)',
    r'<img[^>]*src\s*=\s*["].*?["]'
]
