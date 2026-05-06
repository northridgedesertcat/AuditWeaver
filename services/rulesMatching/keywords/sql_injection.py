# SQL注入关键词配置

# SQL注入关键词
SQL_INJECTION_KEYWORDS = [
    'union', 'select', 'from', 'where', 'drop', 'delete', 'insert', 'update',
    'and', 'or', 'not', 'null', 'order', 'group', 'by', 'having',
    'limit', 'offset', 'like', 'in', 'between', 'as', 'join',
    "'", '"', ';', '--', '#', '/*', '*/'
]

# SQL注入正则模式
SQL_INJECTION_PATTERNS = [
    r'\bunion\b.*\bselect\b',
    r'\bselect\b.*\bfrom\b',
    r'\bwhere\b.*[\'"].*[=<>]',
    r'\bdrop\b.*\btable\b',
    r'\bdelete\b.*\bfrom\b',
    r'\binsert\b.*\binto\b',
    r'\bupdate\b.*\bset\b',
    r'\band\b.*\b1=1\b',
    r'\bor\b.*\b1=1\b',
    r'\bnot\b.*\bnull\b',
    r'\bor\b.*\b\'\'=\'\'\b'
]
