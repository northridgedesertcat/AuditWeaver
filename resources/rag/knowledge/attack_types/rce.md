---
doc_id: attack_types/rce
source: attack_types
attack_type: command_injection
severity: critical
---

# 命令注入 / 远程代码执行 (Command Injection / RCE)

## 原理

命令注入是攻击者将操作系统命令注入到应用程序执行的系统调用中,让服务器执行任意命令的攻击。根因是应用把用户输入拼进 shell 命令(ping、system()、popen()、os.system 等)且未做转义。与 SQL 注入的区别:注入目标是操作系统 shell 而非数据库。成功利用等同服务器沦陷:可读取任意文件、建立反弹 shell、横向移动。命令注入常用元字符:分号 ;(命令分隔)、管道 |(结果传递)、反引号 ` ` 与 $( )(命令替换)、换行符 %0a。

## 典型 payload 特征

常见 payload:127.0.0.1;whoami、127.0.0.1 && cat /etc/passwd、| id、$(whoami)、`id`;命令替换变体:${IFS} 替代空格(cat${IFS}/etc/passwd)绕过空格过滤;Windows 场景:& whoami、| dir C:\、%20%26%20 URL 编码;反弹 shell:nc/bash -i >& /dev/tcp/...;常见注入端点:ping/健康检查 host 参数、文件名处理、导出/压缩功能。工具指纹:sqlmap --os-shell、commix。

## 检测要点

检测维度:参数值中同时出现 IP/主机名与 shell 元字符(; | && ` $( );命令名与敏感路径组合(cat /etc/passwd、/var/log、net user、whoami、id);${IFS} 等 shell 语法;URL 编码的 %3B(%0a)后跟命令词。日志侧关注:目标端点本身不产生命令场景(如 /api/ping 带非 IP 参数值)、响应时间异常(注入 sleep 类命令)、500 状态 + 参数含元字符。文件读取类命令注入常与路径遍历(sensitive_access)伴生。

## ATT&CK 映射

MITRE ATT&CK: T1059 Command and Scripting Interpreter(尤其 T1059.004 Unix Shell / T1059.003 Windows Command);T1190 Exploit Public-Facing Application 作为初始入口;后续常衔接 T1083 File and Directory Discovery、T1078 账号发现。OWASP Top 10 2021:A03:2021 Injection。

## 响置要点

应急响应:立即封禁来源 IP;若怀疑命令已执行,排查进程列表(netstat 异常外连、ps 中的反弹 shell)、crontab 与启动项持久化、新增可疑用户;提取应用服务器执行日志确认注入命令内容。长期修复见 remediation 合集:避免调用 shell(参数化 API)、白名单校验输入、最小权限运行应用账号、命令行元字符黑名单只作纵深防御不作主防线。
