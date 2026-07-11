XSS_KEYWORDS = [
    '<script>', '</script>', '<iframe>', '</iframe>', '<object>', '</object>',
    '<embed>', '</embed>', '<link>', '</link>', '<meta>', '</meta>',
    'javascript:', 'onload=', 'onerror=', 'onclick=', 'onmouseover=',
    'onfocus=', 'onblur=', 'onchange=', 'onkeydown=', 'onkeyup=',
    'onkeypress=', 'onmousedown=', 'onmouseup=', 'onmouseout=',
    'document.write', 'eval(', 'alert(', 'prompt(', 'confirm(',
    'innerHTML', 'outerHTML', 'document.cookie', 'localStorage', 'sessionStorage'
]
