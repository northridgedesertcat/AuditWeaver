# 路径遍历关键词配置

# 路径遍历关键词
PATH_TRAVERSAL_KEYWORDS = [
    '../', '..\\', '..%2f', '..%5c',
    '/etc/', '/var/', '/proc/', '/sys/',
    'C:\\', 'D:\\', 'Windows\\', 'System32\\',
    'passwd', 'shadow', 'hosts', 'httpd.conf'
]

# 路径遍历正则模式
PATH_TRAVERSAL_PATTERNS = [
    r'\.\./',
    r'\.\.\\',
    r'\.\.%2f',
    r'\.\.%5c',
    r'/etc/passwd',
    r'/etc/shadow',
    r'C:\\Windows\\',
    r'C:\\System32\\'
]
