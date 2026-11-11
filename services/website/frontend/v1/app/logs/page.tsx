"use client"

import { useEffect, useRef, useState } from "react"
import { DashboardLayout } from "@/components/layout"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ChevronLeft, ChevronRight, RefreshCw, Search, X } from "lucide-react"
import { apiFetch } from "@/lib/api/client"

interface LogEntry {
  "@timestamp": string | number
  event_id?: string
  log_source?: string
  ip?: string
  method?: string
  path?: string
  status?: number
  event?: { original?: string }
}

interface LogPage {
  data: LogEntry[]
  total: number | null
  next_cursor: string | null
  has_more: boolean
  coverage: { complete: boolean; start_time?: string; end_time?: string }
}

const rangeLabels: Record<string, string> = {
  "15m": "最近 15 分钟", "1h": "最近 1 小时", "6h": "最近 6 小时", "24h": "最近 24 小时",
  "7d": "最近 7 天", "30d": "最近 30 天", "90d": "最近 90 天", custom: "自定义",
}

function formatTime(value: string | number) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN")
}

export default function LogsPage() {
  const [search, setSearch] = useState("")
  const [range, setRange] = useState("24h")
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")
  const [ip, setIp] = useState("")
  const [method, setMethod] = useState("all")
  const [status, setStatus] = useState("")
  const [pages, setPages] = useState<LogPage[]>([])
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [selected, setSelected] = useState<LogEntry | null>(null)
  const activeQuery = useRef<URLSearchParams | null>(null)
  const controller = useRef<AbortController | null>(null)
  const current = pages[page]

  async function load(params: URLSearchParams, append = false) {
    controller.current?.abort()
    const request = new AbortController()
    controller.current = request
    setLoading(true)
    setError("")
    if (!append) {
      setPages([])
      setPage(0)
      setSelected(null)
    }
    try {
      const response = await apiFetch(`/logs/?${params}`, { signal: request.signal })
      const result = await response.json()
      if (!response.ok) throw new Error(response.status === 503 ? "所选范围的日志暂时不可用，可能仍在归档，请稍后重试" : result.error || "日志查询失败")
      if (!result.coverage?.complete) throw new Error("所选时间范围的数据尚未完整归档，请稍后重试")
      if (request.signal.aborted) return
      setPages((previous) => append ? [...previous, result] : [result])
      setPage((previous) => append ? previous + 1 : 0)
      setSelected(null)
    } catch (failure) {
      if (!request.signal.aborted) setError(failure instanceof Error ? failure.message : "日志查询失败")
    } finally {
      if (!request.signal.aborted) setLoading(false)
    }
  }

  function query() {
    const until = range === "custom" ? new Date(end) : new Date()
    const durations: Record<string, number> = { "15m": 900000, "1h": 3600000, "6h": 21600000, "24h": 86400000, "7d": 604800000, "30d": 2592000000, "90d": 7776000000 }
    const from = range === "custom" ? new Date(start) : new Date(until.getTime() - durations[range])
    if (Number.isNaN(from.getTime()) || Number.isNaN(until.getTime()) || from >= until) {
      setError("请选择有效的开始和结束时间")
      return
    }
    const params = new URLSearchParams({ size: "20", start_time: from.toISOString(), end_time: until.toISOString() })
    if (search.trim()) params.set("q", search.trim())
    if (ip.trim()) params.set("ip", ip.trim())
    if (method !== "all") params.set("method", method)
    if (status) params.set("status", status)
    activeQuery.current = params
    void load(params)
  }

  useEffect(() => {
    query()
    return () => controller.current?.abort()
    // The initial query runs once; subsequent queries are submitted by the form.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function next() {
    if (page < pages.length - 1) {
      setPage(page + 1)
      return
    }
    if (current?.next_cursor && activeQuery.current) {
      const params = new URLSearchParams(activeQuery.current)
      params.set("cursor", current.next_cursor)
      void load(params, true)
    }
  }

  return (
    <DashboardLayout title="日志管理" subtitle="日志检索与历史回查">
      <div className="space-y-4 min-w-0">
        <form onSubmit={(event) => { event.preventDefault(); query() }} className="space-y-3 border-b pb-4">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-48 flex-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input aria-label="搜索日志" placeholder="IP、路径或 Event ID" value={search} onChange={(event) => setSearch(event.target.value)} className="pl-9" />
            </div>
            <Select value={range} onValueChange={(value) => setRange(value ?? "24h")}>
              <SelectTrigger className="w-36" aria-label="时间范围"><SelectValue>{rangeLabels[range]}</SelectValue></SelectTrigger>
              <SelectContent>
                <SelectItem value="15m">最近 15 分钟</SelectItem>
                <SelectItem value="1h">最近 1 小时</SelectItem>
                <SelectItem value="6h">最近 6 小时</SelectItem>
                <SelectItem value="24h">最近 24 小时</SelectItem>
                <SelectItem value="7d">最近 7 天</SelectItem>
                <SelectItem value="30d">最近 30 天</SelectItem>
                <SelectItem value="90d">最近 90 天</SelectItem>
                <SelectItem value="custom">自定义</SelectItem>
              </SelectContent>
            </Select>
            <Button type="submit" disabled={loading}><Search className="h-4 w-4" />查询</Button>
            <Button type="button" variant="outline" size="icon" title="刷新日志" aria-label="刷新日志" onClick={query} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
          {range === "custom" && <div className="flex flex-wrap gap-3">
            <label className="space-y-1 text-xs">开始时间<Input aria-label="开始时间" type="datetime-local" value={start} onChange={(event) => setStart(event.target.value)} /></label>
            <label className="space-y-1 text-xs">结束时间<Input aria-label="结束时间" type="datetime-local" value={end} onChange={(event) => setEnd(event.target.value)} /></label>
          </div>}
          <div className="flex flex-wrap items-center gap-2">
            <Input aria-label="筛选 IP" placeholder="筛选 IP" className="w-44" value={ip} onChange={(event) => setIp(event.target.value)} />
            <Select value={method} onValueChange={(value) => setMethod(value ?? "all")}>
              <SelectTrigger className="w-32" aria-label="请求方法"><SelectValue>{method === "all" ? "所有方法" : method}</SelectValue></SelectTrigger>
              <SelectContent>{["all", "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"].map((value) => <SelectItem key={value} value={value}>{value === "all" ? "所有方法" : value}</SelectItem>)}</SelectContent>
            </Select>
            <Input aria-label="状态码" placeholder="状态码" type="number" min={0} max={65535} className="w-28" value={status} onChange={(event) => setStatus(event.target.value)} />
          </div>
        </form>

        {error && <div role="alert" className="border-l-2 border-destructive bg-destructive/10 px-4 py-3 text-sm break-words">{error}</div>}
        {current?.coverage.start_time && <p className="text-xs text-muted-foreground break-words">{formatTime(current.coverage.start_time)} 至 {formatTime(current.coverage.end_time || "")}</p>}
        <div className="min-w-0 overflow-x-auto border-y" aria-busy={loading}>
          <Table>
            <TableHeader><TableRow><TableHead className="min-w-44">时间</TableHead><TableHead>IP</TableHead><TableHead>方法</TableHead><TableHead>路径</TableHead><TableHead>状态</TableHead><TableHead>来源</TableHead></TableRow></TableHeader>
            <TableBody>
              {current?.data.map((log, index) => <TableRow key={log.event_id || index} className="cursor-pointer" onClick={() => setSelected(log)}>
                <TableCell className="text-xs whitespace-nowrap">{formatTime(log["@timestamp"])}</TableCell>
                <TableCell className="font-mono text-xs whitespace-nowrap">{log.ip || "-"}</TableCell>
                <TableCell>{log.method || "-"}</TableCell>
                <TableCell className="max-w-96 truncate" title={log.path}>{log.path || "-"}</TableCell>
                <TableCell>{log.status ?? "-"}</TableCell><TableCell className="whitespace-nowrap">{log.log_source || "-"}</TableCell>
              </TableRow>)}
            </TableBody>
          </Table>
        </div>
        {!current?.data.length && <div className="grid h-40 place-items-center border-b text-sm text-muted-foreground">{loading ? "正在查询..." : error ? "查询未完成" : "所选范围内暂无日志"}</div>}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">第 {page + 1} 页，当前 {current?.data.length || 0} 条{current?.total != null ? `，共 ${current.total.toLocaleString()} 条` : ""}</p>
          <div className="flex gap-2">
            <Button variant="outline" size="icon" title="上一页" aria-label="上一页" disabled={page === 0 || loading} onClick={() => { setPage(page - 1); setSelected(null) }}><ChevronLeft className="h-4 w-4" /></Button>
            <Button variant="outline" size="icon" title="下一页" aria-label="下一页" disabled={!current?.has_more || loading} onClick={next}><ChevronRight className="h-4 w-4" /></Button>
          </div>
        </div>
        {selected && <section className="min-w-0 border-t pt-4 space-y-3">
          <div className="flex items-center justify-between"><h2 className="text-sm font-medium">日志详情</h2><Button variant="ghost" size="icon" title="关闭详情" aria-label="关闭详情" onClick={() => setSelected(null)}><X className="h-4 w-4" /></Button></div>
          <p className="font-mono text-xs break-all">{selected.event_id}</p>
          <pre className="max-h-64 overflow-auto rounded bg-muted p-3 text-xs whitespace-pre-wrap break-all">{selected.event?.original || "原始日志文本缺失"}</pre>
          <pre className="max-h-80 overflow-auto rounded bg-muted p-3 text-xs whitespace-pre-wrap break-all">{JSON.stringify(selected, null, 2)}</pre>
        </section>}
      </div>
    </DashboardLayout>
  )
}
