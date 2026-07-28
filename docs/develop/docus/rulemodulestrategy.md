# 规则匹配模块策略文档

## 一、模块概述

规则匹配模块（`rulesMatching`）是 AuditWeaver 安全审计系统的核心组件，负责从 Kafka 消费结构化日志，通过关键词和正则模式匹配检测多种攻击类型，并将检测结果保存到 Elasticsearch 和 Kafka。

### 模块架构

```
services/rulesMatching/
├── main.py              # 主入口：Kafka消费、调度检测、结果输出
├── config.py            # 基础设施配置（Kafka、ES、日志）
├── match_config.py      # 规则配置（攻击类型、关键词、模式、阈值）
├── utils.py             # 工具函数（匹配、格式化、验证）
├── dataAnalysis/
│   ├── rules_engine.py  # 规则引擎：协调检测流程
│   └── attack_detectors.py  # 攻击检测器：6种攻击类型的具体检测
├── keywords/
│   ├── sql_injection.py     # SQL注入关键词和模式
│   ├── xss.py               # XSS关键词和模式
│   ├── command_injection.py # 命令注入关键词和模式
│   ├── path_traversal.py    # 路径遍历关键词和模式
│   ├── csrf.py              # CSRF关键词和模式
│   └── sensitive_access.py  # 敏感访问关键词和模式
└── dataTransfer/
    ├── data_saver.py        # 数据保存：ES写入、Kafka发送
    └── kafka_producer.py    # Kafka生产者客户端
```

---

## 二、核心工作流程

### 2.1 整体流程

```
Kafka消费 → 日志验证 → 规则引擎检测 → 结果聚合 → 结果输出
    ↓              ↓            ↓            ↓          ↓
  结构化日志   字段校验     6种攻击检测     去重合并   ES/Kafka/本地
```

### 2.2 详细步骤

| 步骤 | 组件 | 功能说明 |
|------|------|----------|
| 1 | `main.py` | 从 Kafka `KAFKA_TOPIC_STRUCTURED` topic 消费消息 |
| 2 | `utils.py:validate_log_entry()` | 验证日志格式，必需字段：`ip`, `path`, `method`, `status` |
| 3 | `rules_engine.py:detect()` | 调用 `AttackDetectors.detect_all()` 进行全类型检测 |
| 4 | `attack_detectors.py` | 并行执行6个检测器，每个检测器进行关键词+模式匹配 |
| 5 | `utils.py:aggregate_results()` | 聚合检测结果（当前为透传函数，直接返回结果） |
| 6 | `data_saver.py` | 攻击日志：保存到 ES + 发送到 Kafka；正常日志：保存到本地文件 |

---

## 三、攻击检测机制

### 3.1 检测原理

每种攻击类型采用 **双重检测机制**：

1. **关键词匹配**：检查日志 `path` 字段中是否包含攻击特征关键词（不区分大小写）
2. **正则模式匹配**：使用正则表达式匹配更复杂的攻击模式（不区分大小写）

**判定公式**：
```
匹配数 = 匹配的关键词数 + 匹配的模式数
如果 匹配数 >= 阈值(默认1) → 判定为攻击
```

### 3.2 工具函数

**关键词匹配** ([utils.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/utils.py#L28-L33))：
```python
def match_keywords(text, keywords):
    matched = []
    for keyword in keywords:
        if keyword.lower() in text.lower():
            matched.append(keyword)
    return matched
```

**正则模式匹配** ([utils.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/utils.py#L17-L25))：
```python
def match_patterns(text, patterns):
    matched = []
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            matched.append(pattern)
    return matched
```

---

## 四、攻击类型定义

### 4.1 攻击类型映射

| 攻击类型常量 | 标识字符串 | 检测器方法 |
|-------------|-----------|-----------|
| `SQL_INJECTION` | `sql_injection` | `detect_sql_injection()` |
| `XSS` | `xss` | `detect_xss()` |
| `COMMAND_INJECTION` | `command_injection` | `detect_command_injection()` |
| `PATH_TRAVERSAL` | `path_traversal` | `detect_path_traversal()` |
| `CSRF` | `csrf` | `detect_csrf()` |
| `SENSITIVE_ACCESS` | `sensitive_access` | `detect_sensitive_access()` |

### 4.2 各类型检测规则

#### 4.2.1 SQL注入 (sql_injection)

**检测目标**：识别尝试操纵数据库查询的攻击

**关键词** ([sql_injection.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/sql_injection.py#L4-L9))：
```python
['union', 'select', 'from', 'where', 'drop', 'delete', 'insert', 'update',
 'and', 'or', 'not', 'null', 'order', 'group', 'by', 'having',
 'limit', 'offset', 'like', 'in', 'between', 'as', 'join',
 "'", '"', ';', '--', '#', '/*', '*/']
```

**正则模式** ([sql_injection.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/sql_injection.py#L12-L23))：
```python
[
    r'\bunion\b.*\bselect\b',    # UNION SELECT 联合查询
    r'\bselect\b.*\bfrom\b',     # SELECT FROM 查询
    r'\bwhere\b.*[\'"].*[=<>]',  # WHERE 条件注入
    r'\bdrop\b.*\btable\b',      # DROP TABLE 删除表
    r'\bdelete\b.*\bfrom\b',     # DELETE FROM 删除数据
    r'\binsert\b.*\binto\b',     # INSERT INTO 插入数据
    r'\bupdate\b.*\bset\b',      # UPDATE SET 更新数据
    r'\band\b.*\b1=1\b',         # AND 1=1 恒真条件
    r'\bor\b.*\b1=1\b',          # OR 1=1 恒真条件
    r'\bnot\b.*\bnull\b',        # NOT NULL 判断
    r'\bor\b.*\b\'\'=\'\'\b'     # OR ''='' 恒真条件
]
```

---

#### 4.2.2 XSS (xss)

**检测目标**：识别跨站脚本攻击

**关键词** ([xss.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/xss.py#L4-L9))：
```python
['<script>', '</script>', '<iframe>', '</iframe>',
 'javascript:', 'onerror=', 'onload=', 'onclick=',
 'eval(', 'alert(', 'prompt(', 'confirm(',
 '<img', 'src=', 'href=', 'data:']
```

**正则模式** ([xss.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/xss.py#L12-L21))：
```python
[
    r'<script[^>]*>.*?</script>',      # script标签
    r'<iframe[^>]*>.*?</iframe>',      # iframe标签
    r'javascript:\s*[^\s]+',           # javascript:协议
    r'on\w+\s*=\s*["].*?["]',          # 事件处理器
    r'eval\s*\(.*?\)',                 # eval()函数
    r'alert\s*\(.*?\)',                # alert()函数
    r'prompt\s*\(.*?\)',               # prompt()函数
    r'confirm\s*\(.*?\)',              # confirm()函数
    r'<img[^>]*src\s*=\s*["].*?["]'   # img标签src属性
]
```

---

#### 4.2.3 命令注入 (command_injection)

**检测目标**：识别操作系统命令注入攻击

**关键词** ([command_injection.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/command_injection.py#L4-L10))：
```python
[';', '&', '|', '`', '$(',
 'cat', 'ls', 'dir', 'rm', 'cp', 'mv',
 'chmod', 'chown', 'mkdir', 'rmdir',
 'ping', 'whoami', 'id', 'uname',
 'cmd.exe', 'bash', 'sh', 'powershell']
```

**正则模式** ([command_injection.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/command_injection.py#L13-L20))：
```python
[
    r';\s*[a-z]+',             # 分号后接命令
    r'&\s*[a-z]+',             # 与号后接命令
    r'\|\s*[a-z]+',            # 管道符后接命令
    r'`[a-z]+`',               # 反引号命令
    r'\$\([a-z]+\)',           # $()命令替换
    r'cmd\.exe\s*/c',          # Windows cmd /c
    r'powershell\s*-c'         # PowerShell -c
]
```

---

#### 4.2.4 路径遍历 (path_traversal)

**检测目标**：识别目录遍历攻击（尝试访问系统敏感文件）

**关键词** ([path_traversal.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/path_traversal.py#L4-L9))：
```python
['../', '..\\', '..%2f', '..%5c',
 '/etc/', '/var/', '/proc/', '/sys/',
 'C:\\', 'D:\\', 'windows\\', 'System32\\',
 'passwd', 'shadow', 'hosts', 'httpd.conf']
```

**正则模式** ([path_traversal.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/path_traversal.py#L12-L20))：
```python
[
    r'\.\./',                  # Unix/Linux路径遍历
    r'\.\.\\',                 # Windows路径遍历
    r'\.\.%2f',                # URL编码../
    r'\.\.%5c',                # URL编码..\
    r'/etc/passwd',            # 敏感文件passwd
    r'/etc/shadow',            # 敏感文件shadow
    r'C:\\windows\\',          # Windows系统目录
    r'C:\\System32\\'          # Windows系统目录
]
```

---

#### 4.2.5 CSRF (csrf)

**检测目标**：识别跨站请求伪造攻击

**关键词** ([csrf.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/csrf.py#L3-L12))：
```python
['csrf', 'token', 'nonce', 'form', 'post', 'get', 'cookie', 'session']
```

**正则模式** ([csrf.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/csrf.py#L14-L17))：
```python
[
    r'\bcsrf\b',               # CSRF关键词
    r'\btoken\b',              # Token关键词
    r'\bnonce\b'               # Nonce关键词
]
```

---

#### 4.2.6 敏感访问 (sensitive_access)

**检测目标**：识别对敏感资源的访问尝试

**关键词** ([sensitive_access.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/sensitive_access.py#L4-L10))：
```python
['admin', 'login', 'signin', 'auth',
 'password', 'passwd', 'secret', 'token',
 'api', 'rest', 'webservice', 'xmlrpc',
 '.git', '.svn', '.hg', 'backup',
 'config', 'settings', 'database']
```

**正则模式** ([sensitive_access.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/rulesMatching/keywords/sensitive_access.py#L13-L26))：
```python
[
    r'\badmin\b',              # 管理后台
    r'\blogin\b',              # 登录页面
    r'\bsignin\b',             # 登录页面
    r'\bauth\b',               # 认证相关
    r'\bpassword\b',           # 密码相关
    r'\bpasswd\b',             # 密码相关
    r'\bsecret\b',             # 秘密信息
    r'\btoken\b',              # Token相关
    r'\bapi\b',                # API接口
    r'\b\.git\b',              # Git仓库
    r'\b\.svn\b',              # SVN仓库
    r'\bbackup\b',             # 备份文件
    r'\bconfig\b'              # 配置文件
]
```

---

## 五、配置参数

### 5.1 检测配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `max_matches` | 5 | 每个日志最多检测出的攻击类型数 |
| `min_confidence` | 0.1 | 最小置信度（当前未使用） |

### 5.2 规则配置

每种攻击类型的配置结构：
```python
{
    'keywords': [...],   # 关键词列表
    'patterns': [...],   # 正则模式列表
    'threshold': 1       # 匹配阈值（默认1）
}
```

### 5.3 日志字段映射

| 字段名 | 来源字段 | 用途 |
|--------|---------|------|
| `ip` | `ip` | 客户端IP |
| `path` | `path` | **检测主字段**：URL路径 |
| `method` | `method` | HTTP方法 |
| `status` | `status` | 响应状态码 |
| `user_agent` | `user_agent` | 用户代理（当前未用于检测） |
| `referrer` | `referrer` | 来源页（当前未用于检测） |

---

## 六、结果输出

### 6.1 攻击日志

**检测结果结构**：
```python
{
    'event_id': 'xxx',                    # 日志事件ID
    'attack_type': ['sql_injection'],     # 攻击类型列表
    'matched_rules': {
        'keywords': ['union', 'select'],  # 匹配的关键词
        'patterns': [r'\bunion\b.*\bselect\b']  # 匹配的模式
    },
    'detection_time': 1234567890,         # 检测时间戳
    'is_attack': True                     # 是否为攻击
}
```

**输出目标**：
1. **Elasticsearch**：索引 `ES_INDEX_MATCHED_LOGS`，文档ID为 `event_id`
2. **Kafka**：发送到 `KAFKA_TOPIC_ANALYSIS` topic

### 6.2 正常日志

未匹配到任何攻击类型的日志：
- 保存到本地目录：`temporaryDatas/unmatchDatas/{YYYY-MM-DD}/{HH}/`
- 文件命名：`normal_log_{timestamp}.json`

---

## 七、关键设计要点

### 7.1 多攻击类型合并

当一条日志匹配多种攻击类型时，`_merge_detections()` 方法会合并结果：
- `attack_type` 字段合并为逗号分隔字符串
- `matched_rules.keywords` 和 `matched_rules.patterns` 去重合并

### 7.2 检测范围限制

当前所有检测器仅对 `path` 字段进行检测，其他字段（如 `user_agent`, `referrer`）尚未参与检测逻辑。

### 7.3 DDoS检测

`ATTACK_TYPES` 中定义了 `DDoS` 类型，但在 `RULES_CONFIG` 中未启用，对应的检测逻辑也未实现。

### 7.4 结果合并机制

当一条日志匹配多种攻击类型时，`DataSaver.save_attack_log()` 方法会调用 `_merge_detections()` 将所有检测结果合并成单一文档：
- 将多种攻击类型合并为逗号分隔字符串
- 对匹配的关键词和模式进行去重
- 最终只向 Elasticsearch 和 Kafka 发送一条消息

**合并后结构**：
```python
{
    'attack_type': 'sql_injection,xss',  # 合并后的攻击类型
    'matched_rules': {
        'keywords': ['union', 'select', '<script>'],  # 去重后的关键词
        'patterns': [...]  # 去重后的模式
    },
    'is_attack': True
}
```

> **历史记录说明**：项目历史中曾记录"重复报告"问题，但当前实现已通过 `_merge_detections()` 解决，同一 `event_id` 只会产生一条分析报告。

---

## 八、扩展建议

1. **扩展检测字段**：将 `user_agent`, `referrer`, `method` 等字段纳入检测范围
2. **实现DDoS检测**：基于IP请求频率的速率限制检测
3. **误报过滤**：增加白名单机制或上下文分析减少误报
4. **置信度计算**：根据匹配数量和类型计算置信度分数
5. **规则热更新**：支持运行时动态加载规则配置
