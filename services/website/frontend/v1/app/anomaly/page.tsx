"use client"

import { useState } from "react"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  AlertTriangle,
  Activity,
  TrendingUp,
  TrendingDown,
  Clock,
  MapPin,
  User,
  Server,
  Eye,
  CheckCircle,
  XCircle,
  ChevronRight,
  Filter,
  RefreshCw,
} from "lucide-react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  ZAxis,
} from "recharts"
import { cn } from "@/lib/utils"

const anomalyTrend = [
  { time: "00:00", anomalies: 3, baseline: 5 },
  { time: "02:00", anomalies: 2, baseline: 4 },
  { time: "04:00", anomalies: 1, baseline: 3 },
  { time: "06:00", anomalies: 4, baseline: 5 },
  { time: "08:00", anomalies: 8, baseline: 6 },
  { time: "10:00", anomalies: 12, baseline: 7 },
  { time: "12:00", anomalies: 15, baseline: 8 },
  { time: "14:00", anomalies: 18, baseline: 9 },
  { time: "16:00", anomalies: 22, baseline: 10 },
  { time: "18:00", anomalies: 14, baseline: 8 },
  { time: "20:00", anomalies: 9, baseline: 6 },
  { time: "22:00", anomalies: 5, baseline: 5 },
]

const anomalyScatter = [
  { x: 100, y: 200, z: 20, name: "SQL 注入尝试" },
  { x: 120, y: 100, z: 40, name: "暴力破解" },
  { x: 170, y: 300, z: 30, name: "异常数据导出" },
  { x: 140, y: 250, z: 25, name: "权限提升" },
  { x: 150, y: 400, z: 35, name: "端口扫描" },
  { x: 110, y: 280, z: 15, name: "敏感文件访问" },
  { x: 200, y: 150, z: 45, name: "异常登录" },
  { x: 180, y: 350, z: 28, name: "数据泄露" },
]

const anomalies = [
  {
    id: "anom-001",
    type: "login_anomaly",
    title: "异常登录行为",
    description: "用户 admin_zhang 从未知 IP 地址登录，与历史行为模式不符",
    severity: "high",
    score: 92,
    timestamp: "2024-01-15 14:32:18",
    source: "Authentication Service",
    details: {
      user: "admin_zhang",
      ip: "185.234.12.45",
      location: "俄罗斯, 莫斯科",
      normalLocation: "中国, 北京",
      loginTime: "14:32 UTC+8",
      normalLoginTime: "09:00-18:00 UTC+8",
    },
    status: "open",
  },
  {
    id: "anom-002",
    type: "data_exfiltration",
    title: "大量数据导出",
    description: "检测到异常大量数据查询和导出操作",
    severity: "critical",
    score: 98,
    timestamp: "2024-01-15 14:28:45",
    source: "Database Monitor",
    details: {
      user: "service_account_01",
      dataVolume: "2.3GB",
      normalVolume: "50MB",
      tables: ["users", "transactions", "sensitive_data"],
      duration: "15 分钟",
    },
    status: "investigating",
  },
  {
    id: "anom-003",
    type: "network_scan",
    title: "内部端口扫描",
    description: "检测到来自内部 IP 的大规模端口扫描活动",
    severity: "medium",
    score: 75,
    timestamp: "2024-01-15 14:15:22",
    source: "Network IDS",
    details: {
      sourceIp: "10.0.1.45",
      scannedPorts: 1024,
      targetRange: "10.0.0.0/16",
      duration: "5 分钟",
    },
    status: "open",
  },
  {
    id: "anom-004",
    type: "privilege_escalation",
    title: "权限提升尝试",
    description: "检测到可能的权限提升攻击尝试",
    severity: "high",
    score: 88,
    timestamp: "2024-01-15 13:58:11",
    source: "HIDS",
    details: {
      user: "developer_li",
      action: "sudo 权限请求",
      command: "sudo cat /etc/shadow",
      server: "prod-web-01",
    },
    status: "resolved",
  },
  {
    id: "anom-005",
    type: "api_abuse",
    title: "API 滥用",
    description: "检测到 API 调用频率异常升高",
    severity: "low",
    score: 62,
    timestamp: "2024-01-15 13:45:33",
    source: "API Gateway",
    details: {
      apiKey: "ak_prod_xxx",
      requests: 15000,
      normalRequests: 1000,
      endpoint: "/api/v1/users",
      period: "1 小时",
    },
    status: "open",
  },
]

const severityConfig = {
  critical: { label: "严重", color: "bg-critical/20 text-critical", dot: "bg-critical" },
  high: { label: "高危", color: "bg-warning/20 text-warning", dot: "bg-warning" },
  medium: { label: "中危", color: "bg-info/20 text-info", dot: "bg-info" },
  low: { label: "低危", color: "bg-success/20 text-success", dot: "bg-success" },
}

const statusConfig = {
  open: { label: "待处理", color: "bg-destructive/20 text-destructive" },
  investigating: { label: "调查中", color: "bg-warning/20 text-warning" },
  resolved: { label: "已解决", color: "bg-success/20 text-success" },
}

export default function AnomalyPage() {
  const [selectedAnomaly, setSelectedAnomaly] = useState<typeof anomalies[0] | null>(null)
  const [severityFilter, setSeverityFilter] = useState("all")

  const filteredAnomalies = severityFilter === "all" 
    ? anomalies 
    : anomalies.filter(a => a.severity === severityFilter)

  return (
    <DashboardLayout
      title="异常检测"
      subtitle="AI 驱动的行为异常与威胁检测"
    >
      <div className="space-y-4">
        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">活跃异常</p>
                  <p className="text-2xl font-bold">12</p>
                </div>
                <div className="rounded-lg bg-destructive/20 p-2">
                  <AlertTriangle className="h-5 w-5 text-destructive" />
                </div>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                <span className="text-destructive">+3</span> 较1小时前
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">今日检测</p>
                  <p className="text-2xl font-bold">47</p>
                </div>
                <div className="rounded-lg bg-primary/20 p-2">
                  <Activity className="h-5 w-5 text-primary" />
                </div>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                <span className="text-success">-12%</span> 较昨日
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">平均风险分</p>
                  <p className="text-2xl font-bold">76.5</p>
                </div>
                <div className="rounded-lg bg-warning/20 p-2">
                  <TrendingUp className="h-5 w-5 text-warning" />
                </div>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                风险等级: 中高
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">平均响应时间</p>
                  <p className="text-2xl font-bold">18分钟</p>
                </div>
                <div className="rounded-lg bg-success/20 p-2">
                  <Clock className="h-5 w-5 text-success" />
                </div>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                <span className="text-success">-5分钟</span> 较上周
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-medium">异常趋势</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={anomalyTrend}>
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
                    <Line
                      type="monotone"
                      dataKey="anomalies"
                      stroke="oklch(0.6 0.25 25)"
                      strokeWidth={2}
                      dot={false}
                      name="异常数"
                    />
                    <Line
                      type="monotone"
                      dataKey="baseline"
                      stroke="oklch(0.65 0.02 260)"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={false}
                      name="基线"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base font-medium">异常分布图</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart>
                    <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.28 0.03 260)" />
                    <XAxis type="number" dataKey="x" name="时间" stroke="oklch(0.65 0.02 260)" fontSize={12} />
                    <YAxis type="number" dataKey="y" name="风险分" stroke="oklch(0.65 0.02 260)" fontSize={12} />
                    <ZAxis type="number" dataKey="z" range={[100, 500]} />
                    <Tooltip
                      cursor={{ strokeDasharray: "3 3" }}
                      contentStyle={{
                        backgroundColor: "oklch(0.18 0.02 260)",
                        border: "1px solid oklch(0.28 0.03 260)",
                        borderRadius: "8px",
                        color: "oklch(0.95 0.01 260)",
                      }}
                      formatter={(value, name, props) => {
                        if (props && props.payload) {
                          return [props.payload.name, "类型"]
                        }
                        return [value, name]
                      }}
                    />
                    <Scatter data={anomalyScatter} fill="oklch(0.65 0.2 250)" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Anomaly List */}
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base font-medium">异常事件列表</CardTitle>
              <div className="flex items-center gap-2">
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
                <Button variant="outline" size="icon">
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[400px]">
                <div className="space-y-2 p-4 pt-0">
                  {filteredAnomalies.map((anomaly) => {
                    const sevConfig = severityConfig[anomaly.severity as keyof typeof severityConfig]
                    const statConfig = statusConfig[anomaly.status as keyof typeof statusConfig]

                    return (
                      <div
                        key={anomaly.id}
                        className={cn(
                          "flex items-start gap-4 rounded-lg border border-border p-4 cursor-pointer transition-colors hover:bg-muted/50",
                          selectedAnomaly?.id === anomaly.id && "bg-muted/50 border-primary/50"
                        )}
                        onClick={() => setSelectedAnomaly(anomaly)}
                      >
                        <div className={cn("mt-1 h-3 w-3 rounded-full shrink-0", sevConfig.dot)} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge className={cn("text-xs", sevConfig.color)}>
                              {sevConfig.label}
                            </Badge>
                            <Badge className={cn("text-xs", statConfig.color)}>
                              {statConfig.label}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {anomaly.timestamp}
                            </span>
                          </div>
                          <h4 className="mt-1 font-medium">{anomaly.title}</h4>
                          <p className="text-sm text-muted-foreground line-clamp-2">
                            {anomaly.description}
                          </p>
                          <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <Server className="h-3 w-3" />
                              {anomaly.source}
                            </span>
                            <span className="flex items-center gap-1">
                              风险分: <strong className="text-foreground">{anomaly.score}</strong>
                            </span>
                          </div>
                        </div>
                        <ChevronRight className="h-5 w-5 text-muted-foreground shrink-0" />
                      </div>
                    )
                  })}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Detail Panel */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-medium">
                {selectedAnomaly ? "异常详情" : "选择查看详情"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {selectedAnomaly ? (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs text-muted-foreground">风险评分</p>
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "text-3xl font-bold",
                        selectedAnomaly.score >= 90 ? "text-critical" :
                        selectedAnomaly.score >= 75 ? "text-warning" :
                        selectedAnomaly.score >= 50 ? "text-info" : "text-success"
                      )}>
                        {selectedAnomaly.score}
                      </span>
                      <span className="text-sm text-muted-foreground">/ 100</span>
                    </div>
                  </div>

                  <div>
                    <p className="text-xs text-muted-foreground mb-2">详细信息</p>
                    <div className="space-y-2">
                      {Object.entries(selectedAnomaly.details).map(([key, value]) => (
                        <div key={key} className="flex justify-between text-sm">
                          <span className="text-muted-foreground">{key}</span>
                          <span className="font-mono text-right max-w-[60%] truncate">
                            {Array.isArray(value) ? value.join(", ") : value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-2 pt-2">
                    <Button size="sm" className="flex-1">
                      <Eye className="mr-2 h-4 w-4" />
                      调查
                    </Button>
                    <Button size="sm" variant="outline" className="flex-1">
                      <CheckCircle className="mr-2 h-4 w-4" />
                      标记已解决
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                  <p className="text-sm">点击左侧列表查看详情</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  )
}
