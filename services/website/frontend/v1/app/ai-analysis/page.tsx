"use client"

import { useState } from "react"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Brain,
  Cpu,
  Activity,
  Target,
  Zap,
  TrendingUp,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Play,
  Pause,
  Settings,
  BarChart3,
  Network,
  Shield,
} from "lucide-react"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from "recharts"
import { cn } from "@/lib/utils"

const modelPerformance = [
  { time: "00:00", accuracy: 94.2, latency: 45 },
  { time: "04:00", accuracy: 94.5, latency: 42 },
  { time: "08:00", accuracy: 95.1, latency: 52 },
  { time: "12:00", accuracy: 94.8, latency: 68 },
  { time: "16:00", accuracy: 95.3, latency: 55 },
  { time: "20:00", accuracy: 95.0, latency: 48 },
]

const analysisCategories = [
  { name: "异常检测", value: 1234, color: "oklch(0.65 0.2 250)" },
  { name: "威胁分类", value: 856, color: "oklch(0.7 0.18 160)" },
  { name: "行为分析", value: 623, color: "oklch(0.65 0.2 280)" },
  { name: "模式识别", value: 445, color: "oklch(0.75 0.15 60)" },
  { name: "风险评估", value: 312, color: "oklch(0.6 0.2 25)" },
]

const aiModels = [
  {
    id: "model-001",
    name: "威胁检测模型 v3.2",
    type: "分类模型",
    status: "running",
    accuracy: 95.3,
    latency: "45ms",
    lastTrained: "2024-01-14",
    tasksProcessed: 12847,
  },
  {
    id: "model-002",
    name: "异常行为分析器",
    type: "异常检测",
    status: "running",
    accuracy: 92.8,
    latency: "78ms",
    lastTrained: "2024-01-13",
    tasksProcessed: 8956,
  },
  {
    id: "model-003",
    name: "用户行为画像",
    type: "聚类模型",
    status: "training",
    accuracy: 89.5,
    latency: "120ms",
    lastTrained: "2024-01-12",
    tasksProcessed: 5623,
  },
  {
    id: "model-004",
    name: "日志模式识别",
    type: "序列模型",
    status: "running",
    accuracy: 94.1,
    latency: "35ms",
    lastTrained: "2024-01-14",
    tasksProcessed: 23456,
  },
]

const recentAnalyses = [
  {
    id: 1,
    type: "威胁检测",
    input: "可疑 SQL 注入请求",
    result: "高风险攻击",
    confidence: 96.5,
    status: "completed",
    time: "2 分钟前",
  },
  {
    id: 2,
    type: "行为分析",
    input: "用户 admin 异常登录模式",
    result: "账户可能被盗",
    confidence: 88.2,
    status: "completed",
    time: "5 分钟前",
  },
  {
    id: 3,
    type: "异常检测",
    input: "服务器流量模式",
    result: "DDoS 攻击前兆",
    confidence: 75.8,
    status: "completed",
    time: "8 分钟前",
  },
  {
    id: 4,
    type: "模式识别",
    input: "防火墙日志批量分析",
    result: "处理中...",
    confidence: 0,
    status: "processing",
    time: "进行中",
  },
  {
    id: 5,
    type: "风险评估",
    input: "新部署服务安全评估",
    result: "中等风险",
    confidence: 82.3,
    status: "completed",
    time: "15 分钟前",
  },
]

const statusConfig = {
  running: { label: "运行中", color: "bg-success/20 text-success", icon: CheckCircle },
  training: { label: "训练中", color: "bg-warning/20 text-warning", icon: Activity },
  stopped: { label: "已停止", color: "bg-muted text-muted-foreground", icon: XCircle },
  error: { label: "异常", color: "bg-destructive/20 text-destructive", icon: AlertTriangle },
}

export default function AIAnalysisPage() {
  const [activeTab, setActiveTab] = useState("overview")

  return (
    <DashboardLayout
      title="AI 分析中心"
      subtitle="智能模型管理与分析任务监控"
    >
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="models">模型管理</TabsTrigger>
          <TabsTrigger value="tasks">分析任务</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {/* Stats */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-primary/20 p-2">
                    <Brain className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">活跃模型</p>
                    <p className="text-2xl font-bold">4</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-success/20 p-2">
                    <Zap className="h-5 w-5 text-success" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">今日分析</p>
                    <p className="text-2xl font-bold">3,470</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-info/20 p-2">
                    <Target className="h-5 w-5 text-info" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">平均准确率</p>
                    <p className="text-2xl font-bold">94.2%</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-warning/20 p-2">
                    <Clock className="h-5 w-5 text-warning" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">平均延迟</p>
                    <p className="text-2xl font-bold">52ms</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Charts */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-medium">模型性能趋势</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={modelPerformance}>
                      <defs>
                        <linearGradient id="colorAccuracy" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="oklch(0.7 0.18 160)" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="oklch(0.7 0.18 160)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.28 0.03 260)" />
                      <XAxis dataKey="time" stroke="oklch(0.65 0.02 260)" fontSize={12} />
                      <YAxis stroke="oklch(0.65 0.02 260)" fontSize={12} domain={[90, 100]} />
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
                        dataKey="accuracy"
                        stroke="oklch(0.7 0.18 160)"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#colorAccuracy)"
                        name="准确率 (%)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base font-medium">分析任务分布</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={analysisCategories} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.28 0.03 260)" />
                      <XAxis type="number" stroke="oklch(0.65 0.02 260)" fontSize={12} />
                      <YAxis dataKey="name" type="category" stroke="oklch(0.65 0.02 260)" fontSize={12} width={80} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "oklch(0.18 0.02 260)",
                          border: "1px solid oklch(0.28 0.03 260)",
                          borderRadius: "8px",
                          color: "oklch(0.95 0.01 260)",
                        }}
                      />
                      <Bar dataKey="value" name="任务数">
                        {analysisCategories.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Recent Analyses */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-medium">最近分析任务</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[300px]">
                <div className="space-y-3">
                  {recentAnalyses.map((analysis) => (
                    <div
                      key={analysis.id}
                      className="flex items-center justify-between rounded-lg border border-border bg-card/50 p-4"
                    >
                      <div className="flex items-center gap-4">
                        <div className={cn(
                          "rounded-lg p-2",
                          analysis.status === "processing" ? "bg-warning/20" : "bg-primary/20"
                        )}>
                          {analysis.status === "processing" ? (
                            <Activity className="h-4 w-4 text-warning animate-pulse" />
                          ) : (
                            <Brain className="h-4 w-4 text-primary" />
                          )}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-xs">
                              {analysis.type}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {analysis.time}
                            </span>
                          </div>
                          <p className="mt-1 text-sm font-medium">{analysis.input}</p>
                          <p className="text-sm text-muted-foreground">{analysis.result}</p>
                        </div>
                      </div>
                      {analysis.status === "completed" && (
                        <div className="text-right">
                          <p className="text-sm text-muted-foreground">置信度</p>
                          <p className={cn(
                            "text-lg font-bold",
                            analysis.confidence >= 90 ? "text-success" :
                            analysis.confidence >= 75 ? "text-warning" : "text-muted-foreground"
                          )}>
                            {analysis.confidence}%
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="models" className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-sm text-muted-foreground">管理和监控所有 AI 模型</p>
            <Button>
              <Settings className="mr-2 h-4 w-4" />
              模型配置
            </Button>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {aiModels.map((model) => {
              const config = statusConfig[model.status as keyof typeof statusConfig]
              const StatusIcon = config.icon

              return (
                <Card key={model.id}>
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-base font-medium">{model.name}</CardTitle>
                        <p className="text-sm text-muted-foreground">{model.type}</p>
                      </div>
                      <Badge className={cn("text-xs", config.color)}>
                        <StatusIcon className="mr-1 h-3 w-3" />
                        {config.label}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs text-muted-foreground">准确率</p>
                        <p className="text-lg font-bold text-success">{model.accuracy}%</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">平均延迟</p>
                        <p className="text-lg font-bold">{model.latency}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">已处理任务</p>
                        <p className="text-sm font-medium">{model.tasksProcessed.toLocaleString()}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">上次训练</p>
                        <p className="text-sm font-medium">{model.lastTrained}</p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {model.status === "running" ? (
                        <Button variant="outline" size="sm" className="flex-1">
                          <Pause className="mr-2 h-4 w-4" />
                          暂停
                        </Button>
                      ) : (
                        <Button variant="outline" size="sm" className="flex-1">
                          <Play className="mr-2 h-4 w-4" />
                          启动
                        </Button>
                      )}
                      <Button variant="outline" size="sm" className="flex-1">
                        <BarChart3 className="mr-2 h-4 w-4" />
                        详情
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </TabsContent>

        <TabsContent value="tasks" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-medium">分析任务队列</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recentAnalyses.map((analysis) => (
                  <div
                    key={analysis.id}
                    className="flex items-center gap-4 rounded-lg border border-border p-4"
                  >
                    <div className={cn(
                      "h-2 w-2 rounded-full",
                      analysis.status === "processing" ? "bg-warning animate-pulse" : "bg-success"
                    )} />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{analysis.type}</span>
                        <Badge variant="outline" className="text-xs">
                          {analysis.status === "processing" ? "处理中" : "已完成"}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{analysis.input}</p>
                    </div>
                    {analysis.status === "completed" && (
                      <div className="text-right">
                        <p className="font-medium">{analysis.confidence}%</p>
                        <p className="text-xs text-muted-foreground">{analysis.time}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </DashboardLayout>
  )
}
