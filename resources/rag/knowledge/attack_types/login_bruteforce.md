---
doc_id: attack_types/login_bruteforce
source: attack_types
attack_type: login_bruteforce
severity: high
---

# 登录暴力破解 (Login Brute-force / 凭据填充)

## 原理

登录暴力破解是攻击者对认证接口反复提交用户名/密码组合,尝试命中有效凭据的攻击。两种形态:针对性爆破(固定用户名 + 密码字典)与凭据填充(Credential Stuffing,用撞库泄露的账号密码批量尝试,命中率更高)。成功即直接接管账号,是数据泄露与内部横移最常见的入口。现代爆破依赖代理池与慢速分发规避速率限制。

## 典型特征

行为特征:单 IP 或单账号在短时间内大量 POST /login(或 /api/auth);失败响应占绝对多数(401/403 高占比);请求体/UA 高度同构(脚本特征:python-requests、curl、Go-http-client 无浏览器头);无伴随静态资源请求(纯接口调用,无 JS/CSS 加载,是脚本与真实浏览器的关键区别);密码字典特征(Password123、admin123 等弱模式);分布式形态下表现为单账号多 IP 的失败序列。

## 检测要点

检测维度:窗口内单 IP 认证失败次数阈值(如 5 分钟 >10 次);单账号跨 IP 失败聚积;失败率接近 100% 且速率稳定(机器特征);UA 为非浏览器指纹;登录请求与后续会话行为断裂(爆破成功后立即访问异常接口)。日志侧关注:POST 到 /login、/api/login、/signin 的 401/403 序列;成功前的长失败序列(命中即沦陷);时间分布(深夜/凌晨集中)。登录爆破常作为敏感访问(sensitive_access)的伴生前兆:拿到凭据后访问 /admin/panel 等。

## ATT&CK 映射

MITRE ATT&CK: T1110 Brute Force(含 T1110.001 Password Guessing、T1110.004 Credential Stuffing);成功后衔接 T1078 Valid Accounts(利用有效账号)、T1539 Steal Web Session Cookie(会话接管)。PRE-attack 阶段的凭据获取也可关联 T1589 Gather Victim Identity Info。

## 响置要点

应急响应:对爆破 IP 限速/封禁;检查成功登录记录——凡在长失败序列后的成功登录一律视为可疑,强制注销并重置密码;核查受影响账号的后续操作(数据导出、权限变更、支付类行为);如开启 MFA 则验证推送疲劳轰炸痕迹。长期修复见 remediation 合集:MFA、登录速率限制 + 账号锁定策略、渐进延迟(exponential backoff)、异常登录告警(新地域/新设备)、密码强度策略与泄露密码黑名单。
