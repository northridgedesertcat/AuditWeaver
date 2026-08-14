"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import { getRiskConfig } from "@/lib/risk-level"

interface Alert {
  id: string
  severity: string
  message: string
  source: string
  time: string
  ip: string
}

const defaultAlerts: Alert[] = [
  {
    id: "1",
    severity: "critical",
    message: "检测到可疑的 SQL 注入攻击",
    source: "Web Application Firewall",
    time: "2 分钟前",
    ip: "192.168.1.105",
  },
  {
    id: "2",
    severity: "high",
    message: "异常登录尝试 - 多次失败后成功",
    source: "Authentication Service",
    time: "8 分钟前",
    ip: "10.0.0.45",
  },
  {
    id: "3",
    severity: "high",
    message: "检测到端口扫描活动",
    source: "Network IDS",
    time: "15 分钟前",
    ip: "172.16.0.88",
  },
  {
    id: "4",
    severity: "medium",
    message: "敏感文件访问尝试",
    source: "File Integrity Monitor",
    time: "23 分钟前",
    ip: "192.168.2.201",
  },
  {
    id: "5",
    severity: "low",
    message: "用户权限变更",
    source: "IAM Service",
    time: "45 分钟前",
    ip: "10.0.1.15",
  },
  {
    id: "6",
    severity: "medium",
    message: "异常数据导出请求",
    source: "Data Loss Prevention",
    time: "1 小时前",
    ip: "192.168.1.78",
  },
]

export function RecentAlerts() {
  const [alerts, setAlerts] = useState<Alert[]>(defaultAlerts)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/v1/dashboard/recent-alerts/")
        const data = await response.json()
        if (data.data && data.data.length > 0) {
          setAlerts(data.data)
        }
      } catch (error) {
        console.error("Failed to fetch recent alerts:", error)
      } finally {
        setLoading(false)
      }
    }

    fetchAlerts()
    const interval = setInterval(fetchAlerts, 10000)

    return () => clearInterval(interval)
  }, [])

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base font-medium">最近告警</CardTitle>
        <Badge variant="outline" className="text-xs">
          {loading ? "加载中..." : "实时更新"}
        </Badge>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[340px]">
          <div className="space-y-1 p-4 pt-0">
            {alerts.map((alert) => {
              const config = getRiskConfig(alert.severity)
              const Icon = config.icon

              return (
                <div
                  key={alert.id}
                  className={cn(
                    "flex items-start gap-3 rounded-lg p-3 transition-colors hover:bg-muted/50",
                    config.twBg
                  )}
                >
                  <Icon className={cn("h-5 w-5 mt-0.5 shrink-0", config.twText)} />
                  <div className="flex-1 space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge className={cn("text-xs", config.twBadge)}>
                        {config.label}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {alert.time}
                      </span>
                    </div>
                    <p className="text-sm font-medium leading-tight">
                      {alert.message}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{alert.source}</span>
                      <span>|</span>
                      <span className="font-mono">{alert.ip}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
