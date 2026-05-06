# 命令注入关键词配置

# 命令注入关键词
COMMAND_INJECTION_KEYWORDS = [
    ';', '&', '|', '`', '$(',
    'cat', 'ls', 'dir', 'rm', 'cp', 'mv',
    'chmod', 'chown', 'mkdir', 'rmdir',
    'ping', 'whoami', 'id', 'uname',
    'cmd.exe', 'bash', 'sh', 'powershell'
]

# 命令注入正则模式
COMMAND_INJECTION_PATTERNS = [
    r';\s*[a-z]+',
    r'&\s*[a-z]+',
    r'\|\s*[a-z]+',
    r'`[a-z]+`',
    r'\$\([a-z]+\)',
    r'cmd\.exe\s*/c',
    r'powershell\s*-c'
]
