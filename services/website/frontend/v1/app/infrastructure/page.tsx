"use client"

import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Server,
  Database,
  Globe,
  Shield,
  Cpu,
  HardDrive,
  MemoryStick,
  Network,
  CheckCircle,
  AlertTriangle,
  XCircle,
} from "lucide-react"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { cn } from "@/lib/utils"

const servers = [
  {
    id: "srv-001",
    name: "web-server-01",
    type: "Web Server",
    status: "healthy",
    cpu: 45,
    memory: 62,
    disk: 38,
    network: "1.2 Gbps",
    uptime: "45 天",
    location: "北京 DC1",
  },
  {
    id: "srv-002",
    name: "web-server-02",
    type: "Web Server",
    status: "healthy",
    cpu: 52,
    memory: 58,
    disk: 42,
    network: "980 Mbps",
    uptime: "45 天",
    location: "北京 DC1",
  },
  {
    id: "srv-003",
    name: "api-gateway",
    type: "API Gateway",
    status: "warning",
    cpu: 89,
    memory: 78,
    disk: 55,
    network: "2.5 Gbps",
    uptime: "30 天",
    location: "北京 DC2",
  },
  {
    id: "srv-004",
    name: "db-primary",
    type: "Database",
    status: "healthy",
    cpu: 35,
    memory: 72,
    disk: 85,
    network: "500 Mbps",
    uptime: "90 天",
    location: "上海 DC1",
  },
  {
    id: "srv-005",
    name: "db-replica",
    type: "Database",
    status: "healthy",
    cpu: 28,
    memory: 65,
    disk: 82,
    network: "450 Mbps",
    uptime: "90 天",
    location: "上海 DC1",
  },
  {
    id: "srv-006",
    name: "cache-server",
    type: "Cache",
    status: "healthy",
    cpu: 22,
    memory: 45,
    disk: 15,
    network: "800 Mbps",
    uptime: "60 天",
    location: "北京 DC1",
  },
  {
    id: "srv-007",
    name: "log-collector",
    type: "Log Server",
    status: "healthy",
    cpu: 55,
    memory: 68,
    disk: 72,
    network: "1.5 Gbps",
    uptime: "45 天",
    location: "北京 DC2",
  },
  {
    id: "srv-008",
    name: "backup-server",
    type: "Backup",
    status: "error",
    cpu: 5,
    memory: 12,
    disk: 95,
    network: "50 Mbps",
    uptime: "0 天",
    location: "深圳 DC1",
  },
]

const performanceData = [
  { time: "00:00", cpu: 35, memory: 58, network: 800 },
  { time: "04:00", cpu: 28, memory: 55, network: 600 },
  { time: "08:00", cpu: 55, memory: 62, network: 1200 },
  { time: "12:00", cpu: 72, memory: 70, network: 1800 },
  { time: "16:00", cpu: 68, memory: 68, network: 1600 },
  { time: "20:00", cpu: 45, memory: 60, network: 1000 },
]

const statusConfig = {
  healthy: { label: "正常", color: "bg-success/20 text-success", icon: CheckCircle },
  warning: { label: "警告", color: "bg-warning/20 text-warning", icon: AlertTriangle },
  error: { label: "异常", color: "bg-destructive/20 text-destructive", icon: XCircle },
}

const infraStats = {
  totalServers: 8,
  healthyServers: 6,
  warningServers: 1,
  errorServers: 1,
  avgCpu: 42,
  avgMemory: 58,
}

export default function InfrastructurePage() {
  return (
    <DashboardLayout
      title="基础设施"
      subtitle="服务器与网络资源监控"
    >
      <div className="space-y-4">
        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <Server className="h-8 w-8 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">总服务器</p>
                  <p className="text-2xl font-bold">{infraStats.totalServers}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="h-8 w-8 text-success" />
                <div>
                  <p className="text-sm text-muted-foreground">正常运行</p>
                  <p className="text-2xl font-bold text-success">{infraStats.healthyServers}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <AlertTriangle className="h-8 w-8 text-warning" />
                <div>
                  <p className="text-sm text-muted-foreground">警告状态</p>
                  <p className="text-2xl font-bold text-warning">{infraStats.warningServers}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <XCircle className="h-8 w-8 text-destructive" />
                <div>
                  <p className="text-sm text-muted-foreground">异常状态</p>
                  <p className="text-2xl font-bold text-destructive">{infraStats.errorServers}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <Cpu className="h-8 w-8 text-primary" />
                <div>
                  <p className="text-sm text-muted-foreground">平均 CPU</p>
                  <p className="text-2xl font-bold">{infraStats.avgCpu}%</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <MemoryStick className="h-8 w-8 text-info" />
                <div>
                  <p className="text-sm text-muted-foreground">平均内存</p>
                  <p className="text-2xl font-bold">{infraStats.avgMemory}%</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Performance Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">性能趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={performanceData}>
                  <defs>
                    <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="oklch(0.65 0.2 250)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="oklch(0.65 0.2 250)" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorMemory" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="oklch(0.7 0.18 160)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="oklch(0.7 0.18 160)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.28 0.03 260)" />
                  <XAxis dataKey="time" stroke="oklch(0.65 0.02 260)" fontSize={12} />
                  <YAxis stroke="oklch(0.65 0.02 260)" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "oklch(0.18 0.02 260)",
                      border: "1px solid oklch(0.28 0.03 260)",
                      borderRadius: "8px",
                      color: "oklch(0.95 0.01 260)",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="cpu"
                    stroke="oklch(0.65 0.2 250)"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorCpu)"
                    name="CPU (%)"
                  />
                  <Area
                    type="monotone"
                    dataKey="memory"
                    stroke="oklch(0.7 0.18 160)"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorMemory)"
                    name="内存 (%)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Server List */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">服务器列表</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {servers.map((server) => {
                const config = statusConfig[server.status as keyof typeof statusConfig]
                const StatusIcon = config.icon

                return (
                  <Card key={server.id} className="bg-muted/30">
                    <CardContent className="p-4 space-y-3">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="font-medium">{server.name}</p>
                          <p className="text-xs text-muted-foreground">{server.type}</p>
                        </div>
                        <Badge className={cn("text-xs", config.color)}>
                          <StatusIcon className="mr-1 h-3 w-3" />
                          {config.label}
                        </Badge>
                      </div>

                      <div className="space-y-2">
                        <div>
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="text-muted-foreground flex items-center gap-1">
                              <Cpu className="h-3 w-3" /> CPU
                            </span>
                            <span>{server.cpu}%</span>
                          </div>
                          <Progress value={server.cpu} className="h-1.5" />
                        </div>
                        <div>
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="text-muted-foreground flex items-center gap-1">
                              <MemoryStick className="h-3 w-3" /> 内存
                            </span>
                            <span>{server.memory}%</span>
                          </div>
                          <Progress value={server.memory} className="h-1.5" />
                        </div>
                        <div>
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="text-muted-foreground flex items-center gap-1">
                              <HardDrive className="h-3 w-3" /> 磁盘
                            </span>
                            <span>{server.disk}%</span>
                          </div>
                          <Progress value={server.disk} className="h-1.5" />
                        </div>
                      </div>

                      <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border">
                        <span>运行时间: {server.uptime}</span>
                        <span>{server.location}</span>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
