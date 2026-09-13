"use client"

/**
 * 审核工作台：队列式处理入口。
 * 待处理（默认）/ 处理中 / 已处理（我处理的）三个 Tab；
 * 头部进度卡对应后端 stats 的 pendingReview / claimedCount / todayProcessed。
 */
import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { apiFetch } from "@/lib/api/client"
import { useAuth } from "@/lib/auth"
import { DashboardLayout } from "@/components/layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Globe,
  Loader2,
  PlayCircle,
  Route,
  Timer,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getRiskConfig } from "@/lib/risk-level"
import {
  getReviewStatusConfig,
  isClaimStale,
  type ReviewStatusKey,
} from "@/lib/review-options"

interface WorkbenchReport {
  id: string
  title: string
  riskLevel: string
  attackType: string
  sourceIp: string
  targetPath: string
  generatedAt: string
  aiConfidence: number
  reviewStatus: ReviewStatusKey
  reviewedBy: string | null
  claimedBy: string | null
  claimedAt: string | null
}

interface WorkbenchStats {
  pendingReview: number
  claimedCount: number
  todayProcessed: number
}

type TabKey = "pending" | "claimed" | "mine"

export default function ReviewWorkbenchPage() {
  const router = useRouter()
  const { user } = useAuth()
  const [tab, setTab] = useState<TabKey>("pending")
  const [stats, setStats] = useState<WorkbenchStats>({
    pendingReview: 0,
    claimedCount: 0,
    todayProcessed: 0,
  })
  const [reports, setReports] = useState<WorkbenchReport[]>([])
  const [loading, setLoading] = useState(true)
  const [claimingId, setClaimingId] = useState<string | null>(null)

  const myDisplayName = user?.display_name || user?.username || ""

  const fetchStats = useCallback(async () => {
    try {
      const resp = await apiFetch("/reports/stats/")
      if (resp.ok) {
        const data = await resp.json()
        setStats({
          pendingReview: data.pendingReview || 0,
          claimedCount: data.claimedCount || 0,
          todayProcessed: data.todayProcessed || 0,
        })
      }
    } catch (error) {
      console.error("获取审核统计失败:", error)
    }
  }, [])

  const fetchReports = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (tab === "pending") {
        params.set("review_status", "pending")
        params.set("ordering", "-risk_score") // 高风险优先
      } else if (tab === "claimed") {
        params.set("review_status", "claimed")
      } else {
        params.set("review_status", "processed")
        params.set("reviewed_by", "me")
      }
      const resp = await apiFetch(`/reports/list/?${params.toString()}`)
      if (resp.ok) {
        const data = await resp.json()
        setReports(data.data || [])
      }
    } catch (error) {
      console.error("获取报告列表失败:", error)
    } finally {
      setLoading(false)
    }
  }, [tab])

  useEffect(() => {
    fetchStats()
  }, [fetchStats])

  useEffect(() => {
    fetchReports()
  }, [fetchReports])

  /** 认领并处理：一步完成 claim + 跳转处理页 */
  const handleClaimAndProcess = async (report: WorkbenchReport) => {
    setClaimingId(report.id)
    try {
      const resp = await apiFetch(`/reports/${report.id}/claim/`, { method: "POST" })
      if (resp.ok) {
        router.push(`/reports/review/${report.id}`)
        return
      }
      const data = await resp.json().catch(() => null)
      alert(data?.error || "认领失败")
      fetchReports()
      fetchStats()
    } catch {
      alert("网络连接失败，请检查后端服务是否运行")
    } finally {
      setClaimingId(null)
    }
  }

  const progressCards = [
    {
      title: "待处理",
      value: stats.pendingReview,
      icon: Clock,
      tw: stats.pendingReview > 0 ? "text-warning bg-warning/10" : "text-success bg-success/10",
    },
    {
      title: "处理中",
      value: stats.claimedCount,
      icon: PlayCircle,
      tw: "text-info bg-info/10",
    },
    {
      title: "今日已处理",
      value: stats.todayProcessed,
      icon: CheckCircle2,
      tw: "text-success bg-success/10",
    },
  ]

  return (
    <DashboardLayout title="审核工作台" subtitle="逐份复核 AI 报告，处理一条少一条">
      <div className="space-y-6">
        {/* 进度卡 */}
        <div className="grid gap-4 sm:grid-cols-3">
          {progressCards.map((card) => {
            const Icon = card.icon
            return (
              <Card key={card.title}>
                <CardContent className="flex items-center gap-3 p-4">
                  <div className={cn("rounded-lg p-2", card.tw)}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">{card.title}</p>
                    <p className="text-2xl font-semibold">{card.value}</p>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* 队列列表 */}
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-base">
                {tab === "pending"
                  ? "待处理队列（风险优先）"
                  : tab === "claimed"
                    ? "处理中"
                    : "我处理过的报告"}
              </CardTitle>
              <Tabs value={tab} onValueChange={(v) => setTab(v as TabKey)}>
                <TabsList>
                  <TabsTrigger value="pending">
                    待处理
                    {stats.pendingReview > 0 && (
                      <Badge variant="secondary" className="ml-1.5 h-5 px-1.5 text-xs">
                        {stats.pendingReview}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="claimed">处理中</TabsTrigger>
                  <TabsTrigger value="mine">已处理</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : reports.length === 0 ? (
              tab === "pending" ? (
                <div className="flex flex-col items-center justify-center py-12 text-success">
                  <CheckCircle2 className="h-12 w-12 mb-3" />
                  <p className="font-medium">队列已清空</p>
                  <p className="text-sm text-muted-foreground">
                    所有待处理报告均已处理完毕
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Clock className="h-12 w-12 mb-4 opacity-50" />
                  <p>{tab === "claimed" ? "暂无处理中的报告" : "你还没有处理过报告"}</p>
                </div>
              )
            ) : (
              <div className="space-y-3">
                {reports.map((report) => {
                  const riskCfg = getRiskConfig(report.riskLevel)
                  const statusCfg = getReviewStatusConfig(report.reviewStatus)
                  const mine = report.claimedBy === myDisplayName
                  const stale = isClaimStale(report.claimedAt)

                  // 处理中 Tab：他人的有效认领不可操作；超时可接管
                  const claimable =
                    report.reviewStatus === "pending" ||
                    (report.reviewStatus === "claimed" && !mine && stale)

                  return (
                    <div
                      key={report.id}
                      className={cn(
                        "rounded-lg border p-4 transition-all hover:shadow-md",
                        riskCfg.twBg,
                      )}
                    >
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                        <div className="min-w-0 flex-1 space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-medium">{report.title}</h3>
                            <Badge className={cn("border", riskCfg.twBadge)}>
                              {riskCfg.label}
                            </Badge>
                            <Badge className={cn("border", statusCfg.twBadge)}>
                              {statusCfg.label}
                              {report.reviewStatus === "processed" && report.reviewedBy
                                ? ` · ${report.reviewedBy}`
                                : ""}
                            </Badge>
                          </div>
                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <AlertTriangle className="h-3.5 w-3.5" />
                              {report.attackType}
                            </span>
                            <span className="flex items-center gap-1 font-mono">
                              <Globe className="h-3.5 w-3.5" />
                              {report.sourceIp}
                            </span>
                            <span className="flex items-center gap-1 truncate max-w-xs">
                              <Route className="h-3.5 w-3.5" />
                              {report.targetPath}
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="h-3.5 w-3.5" />
                              {report.generatedAt}
                            </span>
                          </div>
                        </div>

                        {/* 操作区 */}
                        <div className="flex shrink-0 items-center gap-2">
                          {claimable && (
                            <Button
                              size="sm"
                              className="gap-1.5"
                              variant={report.reviewStatus === "claimed" ? "outline" : "default"}
                              onClick={() => handleClaimAndProcess(report)}
                              disabled={claimingId === report.id}
                            >
                              {claimingId === report.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Timer className="h-4 w-4" />
                              )}
                              {report.reviewStatus === "claimed" ? "接管" : "认领并处理"}
                            </Button>
                          )}
                          {report.reviewStatus === "claimed" && mine && (
                            <Button
                              size="sm"
                              className="gap-1.5"
                              onClick={() => router.push(`/reports/review/${report.id}`)}
                            >
                              继续处理
                              <ChevronRight className="h-4 w-4" />
                            </Button>
                          )}
                          {report.reviewStatus === "claimed" && !mine && !stale && (
                            <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                              <PlayCircle className="h-4 w-4" />
                              {report.claimedBy ?? "他人"} · 处理中
                            </span>
                          )}
                          {report.reviewStatus === "processed" && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="gap-1.5"
                              onClick={() => router.push(`/reports/review/${report.id}`)}
                            >
                              去改判
                              <ChevronRight className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
