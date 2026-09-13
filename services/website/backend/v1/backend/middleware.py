"""
API 尾斜杠修复中间件

背景:前端 Next.js rewrites 在转发时会丢掉 URL 尾斜杠(trailingSlash 配置对
rewrites 不生效),导致 Django 收到 /api/v1/auth/login(无斜杠)。Django 默认
APPEND_SLASH=True 对 GET 会 301 重定向加斜杠,但对 POST 不能重定向(会丢 body),
直接抛 RuntimeError 500。

方案:在 URL 解析前直接重写 request.path_info 补上尾斜杠(不重定向,不丢 POST)。
agent SSE 路径本身不带斜杠(pattern 就是无斜杠),跳过。
"""


class ApiTrailingSlashMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if (
            path.startswith('/api/')
            and not path.startswith('/api/v1/agent')
            and not path.endswith('/')
        ):
            request.path_info = path + '/'
        return self.get_response(request)
