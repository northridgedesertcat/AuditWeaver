---
doc_id: attack_types/webshell_upload
source: attack_types
attack_type: webshell_upload
severity: critical
---

# Webshell 上传 (Webshell Upload)

## 原理

Webshell 上传是攻击者利用文件上传功能(头像、附件、编辑器图片)将可执行脚本(.php/.jsp/.asp)上传到 Web 可执行目录并访问触发,获得持续远程控制通道的攻击。攻击链:上传绕过(黑名单绕过/Content-Type 伪造/MAGIC 签名伪造)→ 文件落盘到可解析路径 → HTTP 访问触发执行 → 拿到命令执行接口(POST 命令参数即回显)。一旦 Webshell 落地,攻击者等同拥有服务器 shell,且大马变种(冰蝎/Behinder、哥斯拉/Godzilla、蚁剑/AntSword)流量加密极难检测。

## 典型特征

上传请求特征:multipart 文件名字段含 .php/.php5/.phtml/.jsp/.jspx 后缀及变体(php3/php4/phar、大小写 PHP、双写 pphphp);Content-Type 伪造为 image/jpeg 但文件头(MAGIC bytes)非 JPEG(GIF89a 头 + PHP 代码混写是经典 polyglot);文件内容含 eval($_POST[、assert(、system(、base64_decode(、gzinflate( 等 Webshell 函数;上传后短时间内出现对该文件的 POST 请求(控制指令)。内存马变体:注册 Filter/Listener 型无文件马,流量仅见加密 POST。工具指纹:中国菜刀 UA、冰蝎/哥斯拉的 Accept 头与固定 Content-Type(application/octet-stream)。

## 检测要点

检测维度:上传接口的文件名后缀黑白名单变体命中;上传成功(200)后对非常规路径(uploads/、attachments/)的 POST;POST 请求体为 base64/AES 加密块(高熵)且回显加密;文件内容侧:服务端扫描上传目录中含 PHP/JSP 语法的"图片"。日志侧关注:上传成功 + 随后同 IP 对上传路径的高频 POST 组合序列;静态目录(本应只读)出现 POST 方法本身就是强信号。Webshell 是路径遍历/命令注入/RCE 利用后的持久化终点,常与 command_injection、path_traversal 事件伴生。

## ATT&CK 映射

MITRE ATT&CK: T1505.003 Server Software Component: Web Shell(持久化);前置利用对应 T1190 Exploit Public-Facing Application;上传后衔接 T1059 Command and Scripting Interpreter(执行命令)、T1071.001 Application Layer Protocol: Web Protocols(HTTP C2 通道)。

## 响置要点

应急响应:立即隔离 Webshell 文件(移动/删除前先取证:记录哈希、修改时间、内容);通过文件 mtime 与 access log 还原落地时间线,回溯上传请求定位上传接口与来源 IP;全面排查可执行目录(uploads、静态目录、临时目录)其他可疑文件;内存马场景需检查 JVM/PHP 进程内存与异常网络连接;检查计划任务/启动项的二级持久化。长期修复见 remediation 合集:上传文件重命名(随机名+白名单后缀)、文件内容 MAGIC 校验、上传目录禁止执行权限(nginx: location ~* ^/uploads/.*\.(php)$ { deny all; })、图片二次渲染、WAF 上传流量检测。
