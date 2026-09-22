---
doc_id: attack_types/directory_bruteforce
source: attack_types
attack_type: directory_bruteforce
severity: medium
---

# 目录暴力破解 (Directory Brute-force / 目录扫描)

## 原理

目录暴力破解是攻击者用字典枚举 Web 服务器上的隐藏路径(后台、备份文件、测试页、旧版本接口),根据响应状态码与长度差异判断存在性的侦察行为。本身不直接造成入侵,但暴露的 /.git/、/backup.sql、/admin 面板常成为后续攻击的跳板。工具:dirb、dirsearch、ffuf、gobuster(高并发特征明显),字典常用 common.txt、big.txt。

## 典型特征

行为特征:单 IP 短时间内对大量不同路径发起 GET(速率远超正常浏览);大量 404 之间夹杂 200/401/403(命中的目录);请求路径呈字典序或常见字典顺序(/admin、/backup、/test、/.git、/.env、/phpmyadmin、/wp-login);UA 常为 dirb/dirsearch/ffuf/gobuster 或伪造浏览器 UA;响应体大小高度规律(404 页面相同长度)。

## 检测要点

检测维度:窗口内单 IP 的 404 率异常(>80% 且请求速率超阈值);路径熵低(字典特征)且覆盖敏感路径词表;同一 IP 对 /.git/config、/.env、/.svn 等版本控制/配置敏感路径的探测。与正常爬虫区分:合法爬虫遵守 robots.txt 且 UA 标识,扫描器无视 robots 且高频。日志侧关注:按 IP 聚合的 404 计数突刺、HEAD 方法探测、路径词表命中率。目录扫描常与 sensitive_access 伴生(扫到备份/配置文件后直接读取)。

## ATT&CK 映射

MITRE ATT&CK: T1595 Active Scanning(侦察阶段,尤其 T1595.003 Wordlist Scanning)、T1592 Gather Victim Host Information;暴露管理面板后衔接 T1110 Brute Force(对后台登录爆破)。属于 PRE 阶段侦察技术,杀伤链最前端。

## 响置要点

应急响应:对扫描 IP 做速率限制或临时封禁;重点排查扫描命中的路径(200/401 的那些)是否真存在敏感资源,存在则立即下线或加访问控制;检查 /.git/、/.svn/、备份压缩包、phpinfo() 页是否可访问。长期修复见 remediation 合集:删除不必要的管理/测试页面、Web 服务器层对字典路径返回统一 404、WAF 扫描器识别规则、对象存储/静态目录权限收敛。
