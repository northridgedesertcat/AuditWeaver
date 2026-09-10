"use client"

import { useState, useEffect } from "react"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Search,
  Filter,
  Download,
  RefreshCw,
  Play,
  Calendar,
  Clock,
  Server,
  Database,
  Globe,
  Shield,
  ChevronLeft,
  ChevronRight,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { apiFetch } from "@/lib/api/client"

interface LogEntry {
  "@timestamp": string
  event_id?: string
  log_source?: string
  event?: {
    original?: string
  }
  [key: string]: unknown
}

const logSources = [
  { name: "所有来源", icon: Server, count: "2.3M" },
  { name: "Web 服务器", icon: Globe, count: "890K" },
  { name: "数据库", icon: Database, count: "456K" },
  { name: "安全设备", icon: Shield, count: "234K" },
  { name: "应用服务", icon: Server, count: "720K" },
]

export default function LogsPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size] = useState(20)

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const response = await apiFetch(`/logs/?page=${page}&size=${size}`)
      const data = await response.json()
      setLogs(data.data || [])
      setTotal(data.total || 0)
    } catch (error) {
      console.error("Failed to fetch logs:", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [page])

  const handleRefresh = () => {
    fetchLogs()
  }

  const handleSearch = () => {
    setPage(1)
    fetchLogs()
  }

  const handlePrevPage = () => {
    if (page > 1) {
      setPage(page - 1)
    }
  }

  const handleNextPage = () => {
    if (page * size < total) {
      setPage(page + 1)
    }
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    } catch {
      return timestamp
    }
  }

  const getSource = (log: LogEntry) => {
    const sources = ["Nginx Access Log", "Application Server", "Database", "Security Service", "API Gateway"]
    const hash = log.event_id?.length || log["@timestamp"]?.length || 0
    return sources[hash % sources.length]
  }

  return (
    <DashboardLayout
      title="日志管理"
      subtitle="集中式日志收集、搜索与分析"
    >
      <div className="space-y-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="搜索日志内容、IP 地址..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 bg-muted/50"
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Select defaultValue="1h">
                  <SelectTrigger className="w-32">
                    <SelectValue placeholder="时间范围" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="15m">最近 15 分钟</SelectItem>
                    <SelectItem value="1h">最近 1 小时</SelectItem>
                    <SelectItem value="6h">最近 6 小时</SelectItem>
                    <SelectItem value="24h">最近 24 小时</SelectItem>
                    <SelectItem value="7d">最近 7 天</SelectItem>
                    <SelectItem value="custom">自定义</SelectItem>
                  </SelectContent>
                </Select>
                <Button variant="outline" size="icon">
                  <Filter className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="icon">
                  <Calendar className="h-4 w-4" />
                </Button>
                <Button onClick={handleSearch}>
                  <Play className="mr-2 h-4 w-4" />
                  查询
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-4">
          <Card className="lg:col-span-1">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">日志来源</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="space-y-1 p-2">
                {logSources.map((source, index) => {
                  const Icon = source.icon
                  return (
                    <button
                      key={source.name}
                      className={cn(
                        "flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors hover:bg-muted",
                        index === 0 && "bg-muted"
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4 text-muted-foreground" />
                        <span>{source.name}</span>
                      </div>
                      <Badge variant="secondary" className="text-xs">
                        {source.count}
                      </Badge>
                    </button>
                  )
                })}
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-3">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div className="flex items-center gap-4">
                <CardTitle className="text-sm font-medium">日志列表</CardTitle>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  <span>实时更新中</span>
                  <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={handleRefresh}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  刷新
                </Button>
                <Button variant="ghost" size="sm">
                  <Download className="mr-2 h-4 w-4" />
                  导出
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[500px]">
                {loading ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="flex items-center gap-2">
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      <span className="text-sm text-muted-foreground">加载中...</span>
                    </div>
                  </div>
                ) : logs.length === 0 ? (
                  <div className="flex items-center justify-center py-12">
                    <span className="text-sm text-muted-foreground">暂无日志数据</span>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow className="hover:bg-transparent">
                        <TableHead className="w-[180px]">时间戳</TableHead>
                        <TableHead className="w-[150px]">Event ID</TableHead>
                        <TableHead className="w-[120px]">来源</TableHead>
                        <TableHead className="w-[120px]">Log Source</TableHead>
                        <TableHead>日志内容</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {logs.map((log, index) => (
                        <TableRow
                          key={log.event_id || `log-${index}`}
                          className={cn(
                            "cursor-pointer",
                            selectedLog?.event_id === log.event_id && "bg-muted/50"
                          )}
                          onClick={() => setSelectedLog(log)}
                        >
                          <TableCell className="font-mono text-xs text-muted-foreground">
                            {formatTimestamp(log["@timestamp"] || "")}
                          </TableCell>
                          <TableCell className="text-sm font-mono">
                            {log.event_id || "-"}
                          </TableCell>
                          <TableCell className="text-sm">
                            {getSource(log)}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {log.log_source || "-"}
                          </TableCell>
                          <TableCell className="max-w-[400px] truncate text-sm">
                            {log.event?.original?.substring(0, 100) || "-"}
                            {log.event?.original?.length > 100 && "..."}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </ScrollArea>
              <div className="flex items-center justify-between border-t border-border px-4 py-3">
                <p className="text-sm text-muted-foreground">
                  显示 {((page - 1) * size) + 1}-{Math.min(page * size, total)} 条，共 {total.toLocaleString()} 条
                </p>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" disabled={page <= 1} onClick={handlePrevPage}>
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="sm" disabled={page * size >= total} onClick={handleNextPage}>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {selectedLog && (
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">日志详情</CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedLog(null)}
                >
                  关闭
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-3">
                  <div>
                    <p className="text-xs text-muted-foreground">时间戳</p>
                    <p className="font-mono text-sm">{formatTimestamp(selectedLog["@timestamp"] || "")}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Event ID</p>
                    <p className="font-mono text-sm">{selectedLog.event_id || "-"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">来源</p>
                    <p className="text-sm">{getSource(selectedLog)}</p>
                  </div>
                </div>
                <div className="space-y-3">
                  <div>
                    <p className="text-xs text-muted-foreground">Log Source</p>
                    <p className="text-sm">{selectedLog.log_source || "-"}</p>
                  </div>
                </div>
              </div>
              <div className="mt-4">
                <p className="text-xs text-muted-foreground mb-2">原始日志内容</p>
                <pre className="rounded-lg bg-muted p-4 text-xs overflow-x-auto max-h-[300px] overflow-y-auto">
                  {selectedLog.event?.original || "无"}
                </pre>
              </div>
              <div className="mt-4">
                <p className="text-xs text-muted-foreground mb-2">完整 JSON</p>
                <pre className="rounded-lg bg-muted p-4 text-xs overflow-x-auto max-h-[300px] overflow-y-auto">
                  {JSON.stringify(selectedLog, null, 2)}
                </pre>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  )
}