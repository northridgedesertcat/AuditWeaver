---
doc_id: attack_types/path_traversal
source: attack_types
attack_type: path_traversal
severity: high
---

# 路径遍历 (Path Traversal / Directory Traversal)

## 原理

路径遍历是攻击者通过构造包含 ../(回溯上级目录)或绝对路径的输入,越过应用限定的目录边界读取任意文件的攻击。根因是应用对文件路径参数(下载、预览、包含功能)未做规范化与边界校验,直接拼接用户输入。危害:读取 /etc/passwd、/etc/shadow(权限允许时)、应用配置文件(数据库连接串、密钥)、源代码,配合文件写入场景可植入 Webshell。URL 形态:../ 序列、URL 编码 %2e%2e%2f、双重编码 %252e、Windows 反斜杠 ..\..\、绝对路径直接注入 /etc/passwd。

## 典型 payload 特征

常见目标文件:Linux 的 /etc/passwd(存在性探测的标准文件)、/etc/shadow、/etc/hosts、/proc/self/environ;Windows 的 C:\windows\system32\config\sam、win.ini、boot.ini、../../windows/win.ini;应用自身:.env、config.php、wp-config.php、WEB-INF/web.xml。常见注入点:文件下载参数(file=、path=、filename=)、模板包含、头像/附件预览。工具指纹:Burp Intruder 的 LFI payload 列表、DirBuster。

## 检测要点

检测维度:参数值含 ../ 或 ..\\ 序列(含编码形态);参数值以 / 或盘符开头(绝对路径注入);参数中出现 passwd、shadow、win.ini、web.xml 等系统/应用文件名;同一参数高频枚举不同路径。日志侧关注:GET 请求 query 中 file/path/download 参数的遍历序列;403/404 状态但参数模式命中的试探流量;与敏感文件访问(sensitive_access)的判定边界:遍历特征 ../ 命中即 path_traversal,直接访问已知敏感路径无 ../ 特征归 sensitive_access,两者常伴生。

## ATT&CK 映射

MITRE ATT&CK: T1083 File and Directory Discovery;读取凭据文件衔接 T1552 Unsecured Credentials(如直接读到 .env 密钥);作为初始漏洞利用对应 T1190 Exploit Public-Facing Application。OWASP Top 10 2021:A01:2021 Broken Access Control 访问控制失效大类。

## 响置要点

应急响应:封禁来源 IP;核对已读文件清单(响应体大小与文件名),重点确认密钥/配置文件是否泄露(泄露则轮换凭据);检查文件写入类端点是否被利用植入 Webshell(新增 php/jsp 文件)。长期修复见 remediation 合集:路径规范化(realpath)+ 白名单根目录前缀校验、文件 ID 间接映射(不传真实路径)、下载目录单独最小权限挂载。
