"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  Shield,
  LayoutDashboard,
  FileText,
  Brain,
  AlertTriangle,
  FileWarning,
  MessageSquareCode,
  Bell,
  Server,
  Globe,
  Settings,
  ChevronLeft,
  ChevronRight,
  Search,
  Sparkles,
  BarChart3,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const navItems = [
  {
    title: "执行概览",
    href: "/",
    icon: LayoutDashboard,
    badge: null,
  },
  {
    title: "日志管理",
    href: "/logs",
    icon: FileText,
    badge: "2.3M",
  },
  {
    title: "日志报告",
    href: "/reports",
    icon: BarChart3,
    badge: null,
  },
  {
    title: "AI 分析中心",
    href: "/ai-analysis",
    icon: Brain,
    badge: null,
  },
  {
    title: "异常检测",
    href: "/anomaly",
    icon: AlertTriangle,
    badge: "12",
  },
  {
    title: "事件报告",
    href: "/incidents",
    icon: FileWarning,
    badge: "3",
  },
  {
    title: "AI 安全智能体",
    href: "/agent",
    icon: MessageSquareCode,
    badge: null,
  },
  {
    title: "告警中心",
    href: "/alerts",
    icon: Bell,
    badge: "28",
  },
  {
    title: "基础设施",
    href: "/infrastructure",
    icon: Server,
    badge: null,
  },
  {
    title: "威胁情报",
    href: "/threat-intel",
    icon: Globe,
    badge: null,
  },
  {
    title: "系统设置",
    href: "/settings",
    icon: Settings,
    badge: null,
  },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const pathname = usePathname()

  return (
    <TooltipProvider>
      <aside
        className={cn(
          "flex h-screen flex-col border-r border-sidebar-border bg-sidebar transition-all duration-300",
          collapsed ? "w-16" : "w-64"
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between border-b border-sidebar-border px-4">
          {!collapsed && (
            <Link href="/" className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
                <Shield className="h-5 w-5 text-primary-foreground" />
              </div>
              <span className="text-lg font-semibold text-sidebar-foreground">
                AuditWeaver
              </span>
            </Link>
          )}
          {collapsed && (
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary mx-auto">
              <Shield className="h-5 w-5 text-primary-foreground" />
            </div>
          )}
        </div>

        {/* Search */}
        {!collapsed && (
          <div className="p-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="搜索..."
                className="h-9 bg-sidebar-accent pl-9 text-sm"
              />
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-2">
          <ul className="space-y-1">
            {navItems.map((item) => {
              const isActive = pathname === item.href
              const Icon = item.icon

              const navLink = (
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-primary"
                      : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
                  )}
                >
                  <Icon className={cn("h-5 w-5 shrink-0", isActive && "text-sidebar-primary")} />
                  {!collapsed && (
                    <>
                      <span className="flex-1">{item.title}</span>
                      {item.badge && (
                        <Badge
                          variant="secondary"
                          className={cn(
                            "h-5 px-1.5 text-xs",
                            item.href === "/anomaly" || item.href === "/incidents" || item.href === "/alerts"
                              ? "bg-destructive/20 text-destructive"
                              : "bg-muted text-muted-foreground"
                          )}
                        >
                          {item.badge}
                        </Badge>
                      )}
                    </>
                  )}
                </Link>
              )

              return (
                <li key={item.href}>
                  {collapsed ? (
                    <Tooltip>
                      <TooltipTrigger>{navLink}</TooltipTrigger>
                      <TooltipContent side="right" className="flex items-center gap-2">
                        {item.title}
                        {item.badge && (
                          <Badge variant="secondary" className="h-5 px-1.5 text-xs">
                            {item.badge}
                          </Badge>
                        )}
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    navLink
                  )}
                </li>
              )
            })}
          </ul>
        </nav>

        {/* AI Assistant Quick Access */}
        {!collapsed && (
          <div className="p-3">
            <Link
              href="/agent"
              className="flex items-center gap-3 rounded-lg bg-primary/10 px-3 py-3 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
            >
              <Sparkles className="h-5 w-5" />
              <span>AI 安全助手</span>
            </Link>
          </div>
        )}

        {/* Collapse Button */}
        <div className="border-t border-sidebar-border p-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-center text-sidebar-foreground/70 hover:text-sidebar-foreground"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4 mr-2" />
                <span>收起</span>
              </>
            )}
          </Button>
        </div>
      </aside>
    </TooltipProvider>
  )
}
