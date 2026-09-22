---
doc_id: attack_types/sensitive_access
source: attack_types
attack_type: sensitive_access
severity: high
---

# 敏感文件访问 (Sensitive File Access)

## 原理

敏感文件访问是攻击者直接请求 Web 服务器上不应公开的敏感资源(配置、备份、版本控制目录、管理后台)的行为。与路径遍历(用 ../ 越界)的区别:sensitive_access 是对已知路径的直接 GET,不依赖遍历序列。资源被访问到即视为泄露:凭据/密钥文件泄露导致横向移动,备份包泄露暴露全部源码与数据结构,.git/ 目录泄露可还原完整代码库。常作为目录扫描的下游动作(扫到 → 直接访问)。

## 典型目标清单

配置与凭据:.env(数据库/SMTP/云密钥)、wp-config.php、config.php、WEB-INF/web.xml、application.yml;备份与导出:backup.sql、db.sql、*.sql.gz、database.sql、dump.zip、site.tar.gz、www.zip;版本控制:.git/config、.git/HEAD、.svn/entries;管理后台:/admin、/admin/panel、/manager/html、/phpmyadmin;信息泄露:server-status、phpinfo.php、.DS_Store、robots.txt 泄露的隐藏路径;云端:.well-known/ 配置、IAM 角色元数据端点(169.254.169.254)。

## 检测要点

检测维度:URL 路径命中敏感词表(.git、.env、backup、dump、config、admin、phpmyadmin、phpinfo);对静态资源目录的 POST 方法(静态目录只应 GET);请求 UA 为扫描器指纹(Wget、curl、python-requests 无浏览器头的单次探测);返回 200 的敏感路径访问(泄露已发生,最高优先级)vs 404/403(试探)。日志侧关注:GET 请求路径前缀直接命中词表;相同 IP 先目录扫描(directory_bruteforce)后访问命中路径的时序关联;下载类响应(Content-Length 大)指向 .sql/.zip 后缀。状态码语义:200 = 已泄露,403 = 存在但被拦截,404 = 试探未命中,均为检测信号但响应优先级完全不同。

## ATT&CK 映射

MITRE ATT&CK: T1592 Gather Victim Host Information(侦察);配置文件读取衔接 T1552 Unsecured Credentials(.env 密钥直接利用)、T1087 Account Discovery(凭据发现);管理面板访问成功衔接 T1078 Valid Accounts。PRE 阶段与初始访问的桥接技术。

## 响置要点

应急响应:对已返回 200 的敏感路径立即处置——下线文件、轮换其中包含的全部凭据(数据库密码、API Key、云密钥);.git 泄露需假定全量源码已泄露,评估代码中的硬编码密钥与逻辑漏洞;备份文件泄露需评估数据合规影响(是否含个人信息,触发通报义务);管理后台被访问则核查登录日志。长期修复见 remediation 合集:Web 服务器配置拒绝敏感路径(nginx location deny)、.git/.svn 不部署到生产、备份文件不入 Web 目录、后台路径加 IP 白名单 + MFA。
