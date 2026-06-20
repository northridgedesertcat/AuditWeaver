"use client"

import { useState } from "react"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Progress } from "@/components/ui/progress"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  FileWarning,
  Clock,
  User,
  Calendar,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Play,
  ChevronRight,
  Download,
  Plus,
  MessageSquare,
  Paperclip,
  Activity,
} from "lucide-react"
import { cn } from "@/lib/utils"

const incidents = [
  {
    id: "INC-2024-001",
    title: "疑似 APT 攻击事件",
    description: "检测到高级持续性威胁攻击特征，多个系统受到影响",
    severity: "critical",
    status: "investigating",
    assignee: "张安全",
    createdAt: "2024-01-15 10:23:45",
    updatedAt: "2024-01-15 14:32:18",
    progress: 45,
    affectedSystems: ["web-server-01", "db-primary", "api-gateway"],
    timeline: [
      { time: "10:23:45", action: "事件创建", user: "AI 系统" },
      { time: "10:30:12", action: "分配给 张安全", user: "系统管理员" },
      { time: "11:15:33", action: "开始调查", user: "张安全" },
      { time: "13:45:22", action: "隔离受影响系统", user: "张安全" },
      { time: "14:32:18", action: "更新调查进展", user: "张安全" },
    ],
  },
  {
    id: "INC-2024-002",
    title: "数据泄露调查",
    description: "发现敏感数据可能被未授权访问",
    severity: "high",
    status: "in_progress",
    assignee: "李响应",
    createdAt: "2024-01-14 16:45:12",
    updatedAt: "2024-01-15 09:18:33",
    progress: 70,
    affectedSystems: ["db-replica-02", "backup-server"],
    timeline: [
      { time: "16:45:12", action: "事件创建", user: "DLP 系统" },
      { time: "17:00:00", action: "分配给 李响应", user: "值班经理" },
      { time: "18:30:45", action: "确认数据范围", user: "李响应" },
      { time: "09:18:33", action: "通知相关部门", user: "李响应" },
    ],
  },
  {
    id: "INC-2024-003",
    title: "DDoS 攻击事件",
    description: "遭受大规模分布式拒绝服务攻击",
    severity: "high",
    status: "resolved",
    assignee: "王防护",
    createdAt: "2024-01-13 08:12:33",
    updatedAt: "2024-01-13 12:45:18",
    progress: 100,
    affectedSystems: ["load-balancer", "cdn-edge"],
    timeline: [
      { time: "08:12:33", action: "攻击检测", user: "WAF 系统" },
      { time: "08:15:00", action: "启动应急响应", user: "王防护" },
      { time: "08:30:22", action: "启用 DDoS 防护", user: "王防护" },
      { time: "10:15:45", action: "攻击流量下降", user: "系统" },
      { time: "12:45:18", action: "事件关闭", user: "王防护" },
    ],
  },
  {
    id: "INC-2024-004",
    title: "内部威胁调查",
    description: "员工账户异常行为需要调查",
    severity: "medium",
    status: "pending",
    assignee: null,
    createdAt: "2024-01-15 13:22:11",
    updatedAt: "2024-01-15 13:22:11",
    progress: 0,
    affectedSystems: ["hr-system"],
    timeline: [
      { time: "13:22:11", action: "事件创建", user: "UEBA 系统" },
    ],
  },
]

const severityConfig = {
  critical: { label: "严重", color: "bg-critical/20 text-critical", dot: "bg-critical" },
  high: { label: "高危", color: "bg-warning/20 text-warning", dot: "bg-warning" },
  medium: { label: "中危", color: "bg-info/20 text-info", dot: "bg-info" },
  low: { label: "低危", color: "bg-success/20 text-success", dot: "bg-success" },
}

const statusConfig = {
  pending: { label: "待处理", color: "bg-muted text-muted-foreground", icon: Clock },
  investigating: { label: "调查中", color: "bg-warning/20 text-warning", icon: Activity },
  in_progress: { label: "处理中", color: "bg-info/20 text-info", icon: Play },
  resolved: { label: "已解决", color: "bg-success/20 text-success", icon: CheckCircle },
  closed: { label: "已关闭", color: "bg-muted text-muted-foreground", icon: XCircle },
}

const incidentStats = {
  total: 47,
  open: 12,
  investigating: 5,
  resolved: 30,
  avgResponseTime: "23分钟",
  avgResolutionTime: "4.2小时",
}

export default function IncidentsPage() {
  const [selectedIncident, setSelectedIncident] = useState<typeof incidents[0] | null>(incidents[0])
  const [statusFilter, setStatusFilter] = useState("all")

  const filteredIncidents = statusFilter === "all" 
    ? incidents 
    : incidents.filter(i => i.status === statusFilter)

  return (
    <DashboardLayout
      title="事件报告"
      subtitle="安全事件管理与响应追踪"
    >
      <div className="space-y-4">
        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6">
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">总事件数</p>
              <p className="text-2xl font-bold">{incidentStats.total}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">待处理</p>
              <p className="text-2xl font-bold text-destructive">{incidentStats.open}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">调查中</p>
              <p className="text-2xl font-bold text-warning">{incidentStats.investigating}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">已解决</p>
              <p className="text-2xl font-bold text-success">{incidentStats.resolved}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">平均响应</p>
              <p className="text-2xl font-bold">{incidentStats.avgResponseTime}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">平均解决</p>
              <p className="text-2xl font-bold">{incidentStats.avgResolutionTime}</p>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <div className="grid gap-4 lg:grid-cols-3">
          {/* Incident List */}
          <Card className="lg:col-span-1">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base font-medium">事件列表</CardTitle>
              <Button size="sm">
                <Plus className="mr-2 h-4 w-4" />
                新建
              </Button>
            </CardHeader>
            <div className="px-4 pb-3">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="筛选状态" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="pending">待处理</SelectItem>
                  <SelectItem value="investigating">调查中</SelectItem>
                  <SelectItem value="in_progress">处理中</SelectItem>
                  <SelectItem value="resolved">已解决</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <CardContent className="p-0">
              <ScrollArea className="h-[500px]">
                <div className="space-y-2 p-4 pt-0">
                  {filteredIncidents.map((incident) => {
                    const sevConfig = severityConfig[incident.severity as keyof typeof severityConfig]
                    const statConfig = statusConfig[incident.status as keyof typeof statusConfig]
                    const StatusIcon = statConfig.icon

                    return (
                      <div
                        key={incident.id}
                        className={cn(
                          "rounded-lg border border-border p-3 cursor-pointer transition-colors hover:bg-muted/50",
                          selectedIncident?.id === incident.id && "bg-muted/50 border-primary/50"
                        )}
                        onClick={() => setSelectedIncident(incident)}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-mono text-muted-foreground">
                            {incident.id}
                          </span>
                          <Badge className={cn("text-xs", sevConfig.color)}>
                            {sevConfig.label}
                          </Badge>
                        </div>
                        <h4 className="font-medium text-sm line-clamp-1">{incident.title}</h4>
                        <div className="mt-2 flex items-center justify-between">
                          <Badge variant="outline" className={cn("text-xs", statConfig.color)}>
                            <StatusIcon className="mr-1 h-3 w-3" />
                            {statConfig.label}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {incident.assignee || "未分配"}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Incident Detail */}
          <Card className="lg:col-span-2">
            {selectedIncident ? (
              <>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-mono text-muted-foreground">
                          {selectedIncident.id}
                        </span>
                        <Badge className={cn("text-xs", severityConfig[selectedIncident.severity as keyof typeof severityConfig].color)}>
                          {severityConfig[selectedIncident.severity as keyof typeof severityConfig].label}
                        </Badge>
                        <Badge className={cn("text-xs", statusConfig[selectedIncident.status as keyof typeof statusConfig].color)}>
                          {statusConfig[selectedIncident.status as keyof typeof statusConfig].label}
                        </Badge>
                      </div>
                      <CardTitle className="text-lg">{selectedIncident.title}</CardTitle>
                    </div>
                    <Button variant="outline" size="sm">
                      <Download className="mr-2 h-4 w-4" />
                      导出报告
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <Tabs defaultValue="overview" className="space-y-4">
                    <TabsList>
                      <TabsTrigger value="overview">概览</TabsTrigger>
                      <TabsTrigger value="timeline">时间线</TabsTrigger>
                      <TabsTrigger value="details">详情</TabsTrigger>
                    </TabsList>

                    <TabsContent value="overview" className="space-y-4">
                      <div>
                        <h4 className="text-sm font-medium mb-2">描述</h4>
                        <p className="text-sm text-muted-foreground">
                          {selectedIncident.description}
                        </p>
                      </div>

                      <div>
                        <h4 className="text-sm font-medium mb-2">处理进度</h4>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-muted-foreground">完成度</span>
                            <span className="font-medium">{selectedIncident.progress}%</span>
                          </div>
                          <Progress value={selectedIncident.progress} className="h-2" />
                        </div>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <div>
                          <h4 className="text-sm font-medium mb-2">负责人</h4>
                          <div className="flex items-center gap-2">
                            <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center">
                              <User className="h-4 w-4 text-primary" />
                            </div>
                            <span className="text-sm">
                              {selectedIncident.assignee || "待分配"}
                            </span>
                          </div>
                        </div>
                        <div>
                          <h4 className="text-sm font-medium mb-2">创建时间</h4>
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Calendar className="h-4 w-4" />
                            {selectedIncident.createdAt}
                          </div>
                        </div>
                      </div>

                      <div>
                        <h4 className="text-sm font-medium mb-2">受影响系统</h4>
                        <div className="flex flex-wrap gap-2">
                          {selectedIncident.affectedSystems.map((system) => (
                            <Badge key={system} variant="outline">
                              {system}
                            </Badge>
                          ))}
                        </div>
                      </div>

                      <div className="flex gap-2 pt-2">
                        <Button className="flex-1">
                          <MessageSquare className="mr-2 h-4 w-4" />
                          添加评论
                        </Button>
                        <Button variant="outline" className="flex-1">
                          <Paperclip className="mr-2 h-4 w-4" />
                          附件
                        </Button>
                      </div>
                    </TabsContent>

                    <TabsContent value="timeline">
                      <ScrollArea className="h-[350px]">
                        <div className="relative pl-6 space-y-4">
                          <div className="absolute left-2 top-2 bottom-2 w-px bg-border" />
                          {selectedIncident.timeline.map((event, index) => (
                            <div key={index} className="relative">
                              <div className="absolute -left-4 top-1 h-3 w-3 rounded-full bg-primary" />
                              <div className="rounded-lg border border-border p-3">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-xs font-mono text-muted-foreground">
                                    {event.time}
                                  </span>
                                  <span className="text-xs text-muted-foreground">
                                    {event.user}
                                  </span>
                                </div>
                                <p className="text-sm">{event.action}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </ScrollArea>
                    </TabsContent>

                    <TabsContent value="details">
                      <div className="space-y-4">
                        <div className="grid gap-4 md:grid-cols-2">
                          <div>
                            <p className="text-xs text-muted-foreground">事件 ID</p>
                            <p className="text-sm font-mono">{selectedIncident.id}</p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">严重程度</p>
                            <p className="text-sm">{severityConfig[selectedIncident.severity as keyof typeof severityConfig].label}</p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">状态</p>
                            <p className="text-sm">{statusConfig[selectedIncident.status as keyof typeof statusConfig].label}</p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">负责人</p>
                            <p className="text-sm">{selectedIncident.assignee || "待分配"}</p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">创建时间</p>
                            <p className="text-sm">{selectedIncident.createdAt}</p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">最后更新</p>
                            <p className="text-sm">{selectedIncident.updatedAt}</p>
                          </div>
                        </div>
                      </div>
                    </TabsContent>
                  </Tabs>
                </CardContent>
              </>
            ) : (
              <div className="flex h-[500px] items-center justify-center text-muted-foreground">
                <p>选择一个事件查看详情</p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </DashboardLayout>
  )
}
