/** @type {import('next').NextConfig} */
const nextConfig = {
  // 保留 URL 尾斜杠,避免 rewrites 转发给 Django 时丢斜杠触发 APPEND_SLASH 500
  trailingSlash: true,
  // 关闭 Next.js 压缩中间件:默认 compress=true 会用 compression 中间件缓冲整个
  // 响应再 gzip 发送,直接杀死 SSE 流式(浏览器收 Accept-Encoding: gzip 时触发,
  // curl 默认不发所以 curl 看似正常但浏览器一次性输出)。SSE 本身靠小 chunk 实时推送,
  // 压缩收益低但缓冲代价高。
  compress: false,
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
    ]
  },
}

export default nextConfig