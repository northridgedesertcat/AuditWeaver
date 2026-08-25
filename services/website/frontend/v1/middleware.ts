import { NextResponse, type NextRequest } from 'next/server'

const PUBLIC = ['/login']

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl
  if (PUBLIC.some((p) => pathname.startsWith(p))) return NextResponse.next()
  // middleware 跑在 Edge,只能读 cookie(localStorage 不可用)
  const token = req.cookies.get('aw_access')?.value
  if (!token) {
    const url = req.nextUrl.clone()
    url.pathname = '/login'
    url.searchParams.set('next', pathname)
    return NextResponse.redirect(url)
  }
  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon|icon|api).*)'],
}
