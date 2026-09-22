---
doc_id: attack_types/sqli
source: attack_types
attack_type: sql_injection
severity: critical
---

# SQL 注入 (SQL Injection)

## 原理

SQL 注入是攻击者将恶意 SQL 片段拼接到应用程序的查询语句中,改变原查询语义,从而读取、篡改或删除数据库内容的攻击。根因是应用程序使用字符串拼接构造 SQL,且未对用户输入做类型校验与转义。成功的注入可导致拖库(数据泄露)、认证绕过(永真式 ' OR '1'='1)、甚至通过 INTO OUTFILE 写文件拿下服务器。

## 典型 payload 特征

常见特征包括:单引号/双引号及其 URL 编码(%27 %22)探测语法错误;注释符 --、#、/* */ 截断原语句;永真式 ' OR '1'='1、admin'-- 绕过登录;UNION SELECT 联合查询拖取其他表数据;时间盲注 payload 如 SLEEP(5)、BENCHMARK();堆叠查询分号后跟第二条 SQL。攻击工具指纹:sqlmap、havij 的 User-Agent(User-Agent 中含 sqlmap 字样是高置信信号)。

## 检测要点

检测维度:请求参数中出现 SQL 语法结构(引号+OR/AND 逻辑、UNION SELECT、注释符、SLEEP/WAITFOR 函数名);同一参数值包含引号与 SQL 关键字组合;错误响应体泄露数据库报错信息(Syntax error、MySQL、ORA- 等);对同一端点大量不同 payload 的枚举式试探。日志侧关注:高频 500/401 状态 + 参数异常组合;query string 中的 %27、UNION%20SELECT 等编码特征。

## ATT&CK 映射

MITRE ATT&CK: T1190 Exploit Public-Facing Application(利用面向公众的应用);数据泄露阶段对应 T1530 Data from Cloud Storage / T1005 Data from Local System。OWASP Top 10 2021 中列为 A03:2021 Injection。

## 响置要点

应急响应:封禁来源 IP;复核该 IP 的历史请求是否已有成功拖库(响应体大小异常、慢查询日志);检查数据库审计日志中异常查询;重置可能泄露的凭据。长期修复见 remediation 合集:参数化查询/预编译语句、ORM、最小权限数据库账号、WAF 拦截规则。
