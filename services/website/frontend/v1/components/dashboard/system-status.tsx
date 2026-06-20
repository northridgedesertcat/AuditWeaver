"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Server, Database, Globe, Shield } from "lucide-react"
import { cn } from "@/lib/utils"

const systemStatus = [
  {
    name: "日志收集器",
    status: "healthy",
    uptime: "99.9%",
    load: 45,
    icon: Server,
    details: "12 个节点运行中",
  },
  {
    name: "数据存储集群",
    status: "healthy",
    uptime: "99.8%",
    load: 62,
    icon: Database,
    details: "存储使用率 62%",
  },
  {
    name: "AI 分析引擎",
    status: "healthy",
    uptime: "99.5%",
    load: 78,
    icon: Shield,
    details: "GPU 使用率 78%",
  },
  {
    name: "API 网关",
    status: "warning",
    uptime: "98.2%",
    load: 89,
    icon: Globe,
    details: "高负载警告",
  },
]

const statusConfig = {
  healthy: {
    label: "正常",
    color: "bg-success",
    badge: "bg-success/20 text-success",
  },
  warning: {
    label: "警告",
    color: "bg-warning",
    badge: "bg-warning/20 text-warning",
  },
  error: {
    label: "异常",
    color: "bg-destructive",
    badge: "bg-destructive/20 text-destructive",
  },
}

export function SystemStatus() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-medium">系统状态</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {systemStatus.map((system) => {
          const config = statusConfig[system.status as keyof typeof statusConfig]
          const Icon = system.icon

          return (
            <div key={system.name} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{system.name}</span>
                </div>
                <Badge className={cn("text-xs", config.badge)}>
                  {config.label}
                </Badge>
              </div>
              <Progress value={system.load} className="h-2" />
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{system.details}</span>
                <span>可用性 {system.uptime}</span>
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
