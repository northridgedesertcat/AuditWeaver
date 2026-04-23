COMMAND_INJECTION_KEYWORDS = [
    ';', '|', '&', '&&', '||', '`', '$(',
    'cmd.exe', 'powershell.exe', 'bash', 'sh', 'zsh', 'ksh',
    'ls', 'dir', 'cat', 'type', 'echo', 'whoami', 'id',
    'pwd', 'cd', 'rm', 'del', 'mv', 'cp', 'mkdir', 'md',
    'rmdir', 'rd', 'chmod', 'chown', 'ping', 'nslookup',
    'dig', 'wget', 'curl', 'wget', 'nc', 'netcat', 'telnet'
]
