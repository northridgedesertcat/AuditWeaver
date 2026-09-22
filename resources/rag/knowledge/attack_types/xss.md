---
doc_id: attack_types/xss
source: attack_types
attack_type: xss
severity: high
---

# 跨站脚本攻击 (XSS, Cross-Site Scripting)

## 原理

XSS 是攻击者将恶意脚本注入到其他用户浏览的页面中,在受害者浏览器上下文执行的攻击。根因是应用程序将未净化的用户输入直接渲染进 HTML/JS。按执行路径分三类:反射型(Reflected,恶意脚本来自当前请求参数并被原样回显)、存储型(Stored,payload 持久化到数据库,每个访问者触发,危害最大)、DOM 型(前端 JS 从 location/document.cookie 取值后不安全地写入 DOM)。危害:会话窃取(document.cookie 外带)、键盘记录、钓鱼表单、蠕虫式传播。

## 典型 payload 特征

常见 payload:<script>alert(1)</script> 及其变体 <scr<script>ipt>(绕过黑名单过滤)、<img src=x onerror=alert(1)>(事件处理器注入)、<svg onload=alert(1)>、javascript: 伪协议、document.cookie / document.location 外带数据、encodeURIComponent 编码的 %3Cscript%3E(URL 编码形态)。存储型常见于评论区、用户昵称、私信等回显点。

## 检测要点

检测维度:请求参数中出现 HTML 标签结构(<tag>、onerror=、onload= 等事件属性);javascript: 伪协议;script/img/svg 标签与 alert/prompt/confirm 调试函数组合;URL 编码后的标签 %3Cscript%3E。日志侧关注:query/body 中携带标签语法 + 事件属性的组合;同一用户向富文本字段提交含脚本结构的输入。注意与合法富文本编辑器流量区分(编辑器提交会带 HTML 但通常无事件属性与外带 URL)。

## ATT&CK 映射

MITRE ATT&CK: T1189 Drive-by Compromise(水坑攻击的投递手段)、T1204.003 User Execution: Malicious File(诱骗点击场景);凭据窃取对应 T1539 Steal Web Session Cookie。OWASP Top 10 2021:A03:2021 Injection 注入大类。

## 响置要点

应急响应:封禁来源 IP;若是存储型 XSS,立即定位并清理持久化 payload(评论区/资料字段);检查是否有用户会话异常(异地登录、令牌滥用);评估 payload 是否含外带地址,如是则排查受害范围。长期修复见 remediation 合集:输出编码(Context-Based Encoding)、CSP 内容安全策略、HttpOnly Cookie、输入白名单校验。
