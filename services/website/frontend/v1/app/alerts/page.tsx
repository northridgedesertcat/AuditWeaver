"use client"

import { useState } from "react"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Bell,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle,
  XCircle,
  Clock,
  Filter,
  Settings,
  Volume2,
  VolumeX,
  Eye,
  Trash2,
  ChevronRight,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { formatRelative } from "@/lib/time"

const alerts = [
  {
    id: "alert-001",
    title: "SQL 注入攻击检测",
    description: "检测到来自 185.234.12.45 的 SQL 注入攻击尝试",
    severity: "critical",
    status: "active",
    source: "Web Application Firewall",
    timestamp: Date.now() - 1000 * 60 * 30,
    count: 12,
  },
  {
    id: "alert-002",
    title: "异常登录行为",
    description: "用户 admin_zhang 从异常地点登录",
    severity: "high",
    status: "active",
    source: "Authentication Service",
    timestamp: Date.now() - 1000 * 60 * 35,
    count: 1,
  },
  {
    id: "alert-003",
    title: "端口扫描活动",
    description: "检测到内部 IP 10.0.1.45 进行大规模端口扫描",
    severity: "high",
    status: "investigating",
    source: "Network IDS",
    timestamp: Date.now() - 1000 * 60 * 50,
    count: 1024,
  },
  {
    id: "alert-004",
    title: "SSL 证书即将过期",
    description: "生产环境 SSL 证书将在 15 天后过期",
    severity: "medium",
    status: "active",
    source: "Certificate Monitor",
    timestamp: Date.now() - 1000 * 60 * 60 * 6,
    count: 1,
  },
  {
    id: "alert-005",
    title: "API 速率限制超出",
    description: "API 密钥 ak_prod_xxx 超出速率限制",
    severity: "low",
    status: "resolved",
    source: "API Gateway",
    timestamp: Date.now() - 1000 * 60 * 60 * 6.5,
    count: 15000,
  },
  {
    id: "alert-006",
    title: "磁盘空间警告",
    description: "服务器 db-primary 磁盘使用率达到 85%",
    severity: "medium",
    status: "active",
    source: "Infrastructure Monitor",
    timestamp: Date.now() - 1000 * 60 * 60 * 8,
    count: 1,
  },
  {
    id: "alert-007",
    title: "可疑文件上传",
    description: "检测到可能包含恶意代码的文件上传",
    severity: "high",
    status: "resolved",
    source: "Antivirus Scanner",
    timestamp: Date.now() - 1000 * 60 * 60 * 16,
    count: 3,
  },
  {
    id: "alert-008",
    title: "数据库连接池耗尽",
    description: "应用服务器连接池使用率达到 95%",
    severity: "medium",
    status: "resolved",
    source: "Database Monitor",
    timestamp: Date.now() - 1000 * 60 * 60 * 19,
    count: 1,
  },
]

const alertRules = [
  { id: 1, name: "SQL 注入检测", enabled: true, severity: "critical", notifications: true },
  { id: 2, name: "暴力破解检测", enabled: true, severity: "high", notifications: true },
  { id: 3, name: "异常登录检测", enabled: true, severity: "high", notifications: true },
  { id: 4, name: "端口扫描检测", enabled: true, severity: "medium", notifications: false },
  { id: 5, name: "SSL 证书监控", enabled: true, severity: "medium", notifications: true },
  { id: 6, name: "磁盘空间监控", enabled: false, severity: "low", notifications: false },
]

const severityConfig = {
  critical: { label: "严重", color: "bg-critical/20 text-critical", icon: AlertCircle },
  high: { label: "高危", color: "bg-warning/20 text-warning", icon: AlertTriangle },
  medium: { label: "中危", color: "bg-info/20 text-info", icon: Info },
  low: { label: "低危", color: "bg-success/20 text-success", icon: CheckCircle },
}

const statusConfig = {
  active: { label: "活跃", color: "bg-destructive/20 text-destructive" },
  investigating: { label: "调查中", color: "bg-warning/20 text-warning" },
  resolved: { label: "已解决", color: "bg-success/20 text-success" },
}

export default function AlertsPage() {
  const [severityFilter, setSeverityFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")

  const filteredAlerts = alerts.filter((alert) => {
    if (severityFilter !== "all" && alert.severity !== severityFilter) return false
    if (statusFilter !== "all" && alert.status !== statusFilter) return false
    return true
  })

  const alertCounts = {
    total: alerts.length,
    critical: alerts.filter((a) => a.severity === "critical").length,
    high: alerts.filter((a) => a.severity === "high").length,
    active: alerts.filter((a) => a.status === "active").length,
  }

  return (
    <DashboardLayout
      title="告警中心"
      subtitle="安全告警监控与管理"
    >
      <Tabs defaultValue="alerts" className="space-y-4">
        <TabsList>
          <TabsTrigger value="alerts">告警列表</TabsTrigger>
          <TabsTrigger value="rules">告警规则</TabsTrigger>
        </TabsList>

        <TabsContent value="alerts" className="space-y-4">
          {/* Stats */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">总告警</p>
                    <p className="text-2xl font-bold">{alertCounts.total}</p>
                  </div>
                  <Bell className="h-8 w-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">严重告警</p>
                    <p className="text-2xl font-bold text-critical">{alertCounts.critical}</p>
                  </div>
                  <AlertCircle className="h-8 w-8 text-critical" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">高危告警</p>
                    <p className="text-2xl font-bold text-warning">{alertCounts.high}</p>
                  </div>
                  <AlertTriangle className="h-8 w-8 text-warning" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">待处理</p>
                    <p className="text-2xl font-bold text-destructive">{alertCounts.active}</p>
                  </div>
                  <Clock className="h-8 w-8 text-destructive" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Filters */}
          <Card>
            <CardContent className="p-4">
              <div className="flex flex-wrap items-center gap-4">
                <Select value={severityFilter} onValueChange={setSeverityFilter}>
                  <SelectTrigger className="w-32">
                    <SelectValue placeholder="严重程度" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部</SelectItem>
                    <SelectItem value="critical">严重</SelectItem>
                    <SelectItem value="high">高危</SelectItem>
                    <SelectItem value="medium">中危</SelectItem>
                    <SelectItem value="low">低危</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-32">
                    <SelectValue placeholder="状态" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部</SelectItem>
                    <SelectItem value="active">活跃</SelectItem>
                    <SelectItem value="investigating">调查中</SelectItem>
                    <SelectItem value="resolved">已解决</SelectItem>
                  </SelectContent>
                </Select>
                <div className="flex-1" />
                <Button variant="outline">
                  <Filter className="mr-2 h-4 w-4" />
                  更多筛选
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Alert List */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-medium">
                告警列表 ({filteredAlerts.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[500px]">
                <div className="space-y-2 p-4 pt-0">
                  {filteredAlerts.map((alert) => {
                    const sevConfig = severityConfig[alert.severity as keyof typeof severityConfig]
                    const statConfig = statusConfig[alert.status as keyof typeof statusConfig]
                    const SeverityIcon = sevConfig.icon

                    return (
                      <div
                        key={alert.id}
                        className="flex items-start gap-4 rounded-lg border border-border p-4 transition-colors hover:bg-muted/50"
                      >
                        <SeverityIcon className={cn("h-5 w-5 mt-0.5 shrink-0", sevConfig.color.split(" ")[1])} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge className={cn("text-xs", sevConfig.color)}>
                              {sevConfig.label}
                            </Badge>
                            <Badge className={cn("text-xs", statConfig.color)}>
                              {statConfig.label}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {formatRelative(alert.timestamp)}
                            </span>
                          </div>
                          <h4 className="mt-1 font-medium">{alert.title}</h4>
                          <p className="text-sm text-muted-foreground">{alert.description}</p>
                          <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
                            <span>来源: {alert.source}</span>
                            <span>触发次数: {alert.count}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <CheckCircle className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="rules" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base font-medium">告警规则配置</CardTitle>
              <Button>
                <Settings className="mr-2 h-4 w-4" />
                添加规则
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {alertRules.map((rule) => {
                  const sevConfig = severityConfig[rule.severity as keyof typeof severityConfig]

                  return (
                    <div
                      key={rule.id}
                      className="flex items-center justify-between rounded-lg border border-border p-4"
                    >
                      <div className="flex items-center gap-4">
                        <Switch checked={rule.enabled} />
                        <div>
                          <p className="font-medium">{rule.name}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge className={cn("text-xs", sevConfig.color)}>
                              {sevConfig.label}
                            </Badge>
                            {rule.notifications ? (
                              <Volume2 className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <VolumeX className="h-4 w-4 text-muted-foreground" />
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button variant="ghost" size="sm">
                          编辑
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </DashboardLayout>
  )
}
