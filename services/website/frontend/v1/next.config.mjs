/** @type {import('next').NextConfig} */
const nextConfig = {
  // 保留 URL 尾斜杠,避免 rewrites 转发给 Django 时丢斜杠触发 APPEND_SLASH 500
  trailingSlash: true,
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