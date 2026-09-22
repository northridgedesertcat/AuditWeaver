---
doc_id: remediation/remediation
source: remediation
attack_type: general
severity: high
---

# 安全漏洞修复建议合集 (Remediation Playbook)

## SQL 注入修复:参数化查询

根治方案是参数化查询/预编译语句(Prepared Statement):SQL 模板与数据分离,数据永远不会被解析为 SQL 语法。Python 用 DB-API 的参数占位符(cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))),Java 用 PreparedStatement,禁止字符串拼接 SQL。MyBatis 场景 ${} 是拼接(危险)、#{} 是参数化(安全)。纵深防御:数据库账号最小权限(应用账号不给 DROP/FILE 权限)、错误信息不回传用户(防报错注入)、WAF 注入规则、输入按类型强转(数字参数 int() 强转)。

## XSS 修复:输出编码与 CSP

按输出上下文编码(Context-Based Output Encoding):HTML 上下文用 HTML 实体编码(< → &lt;)、属性上下文加引号并编码、JS 上下文用 JSON 序列化 + 转义、URL 上下文 urlencode。框架默认安全:Django/Jinja2 自动转义,React 默认转义(避免 dangerouslySetInnerHTML)。纵深防御:Content-Security-Policy(response header 限制 script-src 'self')阻断内联脚本执行、Cookie 加 HttpOnly(禁止 JS 读取 document.cookie)与 Secure、富文本输入用白名单过滤器(blewach/bleach 库)。不要依赖输入过滤黑名单对抗 XSS,输出编码才是正确层次。

## 命令注入修复:避免 shell 调用

根治:不调用 shell。用语言原生的参数化 API 代替命令拼接——Python 用 subprocess.run(["ping", "-c", "1", host], shell=False)(列表参数不经 shell 解析,元字符失去语义)、shutil 代替 rm/cp;Java 用 ProcessBuilder。必须传文件名/主机名时做白名单正则校验(如 ^[a-zA-Z0-9.\-]+$ 不含元字符)。纵深防御:应用运行账号最小权限(非 root)、seccomp/容器限制可执行命令面、命令执行结果不直接回显。禁止方案:黑名单过滤 ; | & 转义后仍拼 shell 字符串(编码绕过层出不穷,不能作主防线)。

## 路径遍历修复:路径规范化与白名单

根治:文件访问改为 ID 间接映射(数据库存 ID → 真实路径,用户只传 ID,不传路径)。必须接受路径时:规范化后校验前缀——Python os.path.realpath(user_path) 后检查 startswith(允许的根目录),Java 用 canonical path 对比;文件名白名单正则;拒绝绝对路径输入与 .. 序列(编码后二次校验)。纵深防御:文件服务与 Web 服务分离(静态资源专用最小权限目录)、下载目录禁执行权限、chroot/容器隔离文件系统视图。注意:仅做字符串 replace("../", "") 是错误修复(可用 ....// 绕过),必须规范化后校验。

## 文件上传与 Webshell 修复

上传链路五道闸:①白名单后缀(jpg/png/gif 白名单制,不用黑名单)+ 随机重命名文件(剥离用户可控文件名);②文件内容 MAGIC bytes 校验(claim 是 jpg 就必须以 \xFF\xD8 开头)+ 图片二次渲染(ImageMagick/Pillow 重编码抹除附加 payload);③存储目录去执行权限——nginx 对上传目录 location 配置禁脚本解析、Apache php_admin_flag engine off;④存储与 Web 分离(对象存储 OSS/S3 + 临时签名 URL,不落 Web 盘);⑤ WAF 检测上传内容中的脚本特征。应急侧:部署后定期扫描可执行目录(cksy/isuck 类工具:按文件内容而非后缀识别 Webshell)。

## 认证与暴力破解防护

分层防护:①账号侧——MFA 多因素认证(最强防线)、登录失败锁定(5 次失败锁定 15 分钟,注意防止账号锁定型 DoS:对 IP 而非仅账号锁定)、密码策略(最小长度 + 泄露密码黑名单 HIBP);②网络侧——登录接口 IP 速率限制(Nginx limit_req: 5r/m burst=10)、验证码/渐进延迟(失败次数越多响应越慢,拖垮爆破经济性);③监控侧——异常登录告警(新 IP/新设备/异地/凌晨)、单账号跨 IP 失败聚积告警、成功登录前的长失败序列实时阻断。凭据填充专用:密码泄露库比对(强制命中用户改密)、设备指纹。

## 访问控制与敏感文件暴露修复

敏感路径收敛清单:①Web 服务器层显式 deny——nginx: location ~ /\.(git|svn|env) { deny all; } + location ~* ^/(backup|dump).*\.(sql|zip|tar\.gz)$ { deny all; };②部署卫生——.git/.svn 目录不进生产镜像(CI 构建时 .dockerignore/.gitignore 把关)、备份任务输出到非 Web 目录、phpinfo/debug 页生产环境删除;③后台防护——管理路径非默认(/admin 改不可猜测路径)+ IP 白名单 + MFA,或干脆内网化(VPN 后可达);④响应最小化——server_tokens off、错误页不泄露堆栈、目录列表(autoindex)关闭;⑤元数据端点(169.254.169.254)出方向防火墙封禁,防 SSRF 链。

## 通用纵深防御原则

所有注入类漏洞的共性修复哲学:①数据与代码分离——参数化(SQL 预编译、shell 列表参数、模板自动转义)是根治,过滤/转义是缓解;②最小权限——应用账号、文件系统、数据库权限都按"只够用"收敛,沦陷影响面最小化;③白名单优于黑名单——允许合法(白名单)永远比枚举非法(黑名单)可靠;④纵深防御——修复 + WAF + 监控告警三层,假设任何一层会被绕过;⑤失败安全(fail secure)——校验失败一律拒绝并显式报错,不静默降级。
