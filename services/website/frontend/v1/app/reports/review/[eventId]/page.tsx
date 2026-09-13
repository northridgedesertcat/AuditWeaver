"use client"

/**
 * 报告处理页：左侧报告证据（滚动），右侧 sticky 审核表单。
 * pending → 「开始处理（认领）」；claimed 自己 → 直接表单；他人未超时 → 只读锁定
 * （超时可接管）；processed → 重新审核（预填改判）。提交成功 1.5s 后自动进入下一条。
 */
import { useCallback, useEffect, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api/client"
import { DashboardLayout } from "@/components/layout"
import { ReviewForm, type ReviewSubmitResult } from "@/components/review/review-form"
import { ReviewHistoryTimeline } from "@/components/review/review-history-timeline"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Brain,
  CheckCircle2,
  Clock,
  FileText,
  Globe,
  Hand,
  History,
  Loader2,
  Route,
  Shield,
  Target,
  User,
  Zap,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getRiskConfig, getConfidenceColor } from "@/lib/risk-level"
import {
  getReviewStatusConfig,
  isClaimStale,
} from "@/lib/review-options"

interface OriginalRiskData {
  event_id: string
  ip: string
  log_timestamp: string
  user_agent: string
  status: number
  path: string
  original_log: string
}

interface ReviewData {
  verdict: string
  verdictLabel: string
  category: string
  categoryLabel: string
  actions: string[]
  actionLabels: string[]
  comment: string
  reviewer: string | null
  reviewerDisplayName: string | null
  createdAt: string
  updatedAt: string
  changeType: string
}

interface ReportDetail {
  id: string
  title: string
  riskLevel: string
  attackType: string
  confidence: number
  riskScore: number
  generatedAt: string
  summary: string
  reasoning: string[]
  recommendations: string[]
  originalRiskData: OriginalRiskData
  reviewStatus: "pending" | "claimed" | "processed"
  claimedBy: string | null
  claimedAt: string | null
  reviewedBy: string | null
  reviewedAt: string | null
  review: ReviewData | null
}

type PageMode = "loading" | "claim-gate" | "form" | "locked" | "success"

export default function ReviewProcessingPage() {
  const params = useParams<{ eventId: string }>()
  const eventId = params?.eventId
  const router = useRouter()

  const [detail, setDetail] = useState<ReportDetail | null>(null)
  const [mode, setMode] = useState<PageMode>("loading")
  const [error, setError] = useState<string | null>(null)
  const [claiming, setClaiming] = useState(false)
  const [successData, setSuccessData] = useState<ReviewSubmitResult | null>(null)
  const [historyKey, setHistoryKey] = useState(0)
  const jumpTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadDetail = useCallback(async () => {
    setMode("loading")
    setDetail(null)
    setSuccessData(null)
    try {
      const resp = await apiFetch(`/reports/${eventId}/`)
      if (resp.ok) {
        const data: ReportDetail = await resp.json()
        setDetail(data)
        setError(null)
        // 状态 → 页面模式
        if (data.reviewStatus === "pending") {
          setMode("claim-gate")
        } else if (data.reviewStatus === "processed") {
          setMode("form") // 改判：表单预填当前结论
        } else if (isClaimStale(data.claimedAt)) {
          setMode("claim-gate") // 超时：等同可认领（接管）
        } else {
          setMode("locked") // 他人处理中
        }
      } else {
        const data = await resp.json().catch(() => null)
        setError(data?.error || `无法加载报告详情（HTTP ${resp.status}）`)
      }
    } catch {
      setError("网络连接失败，请检查后端服务是否运行")
    }
  }, [eventId])

  useEffect(() => {
    if (!eventId) return
    loadDetail()
    return () => {
      if (jumpTimer.current) clearTimeout(jumpTimer.current)
    }
  }, [eventId, loadDetail])

  const handleClaim = async () => {
    if (!detail) return
    setClaiming(true)
    try {
      const resp = await apiFetch(`/reports/${detail.id}/claim/`, { method: "POST" })
      if (resp.ok) {
        // 认领成功（含超时接管）→ 进入表单
        setDetail((prev) =>
          prev ? { ...prev, reviewStatus: "claimed", claimedAt: new Date().toLocaleString("zh-CN") } : prev,
        )
        setMode("form")
      } else {
        const data = await resp.json().catch(() => null)
        setError(data?.error || "认领失败")
        loadDetail()
      }
    } catch {
      setError("网络连接失败，请检查后端服务是否运行")
    } finally {
      setClaiming(false)
    }
  }

  const handleReviewSuccess = (data: ReviewSubmitResult) => {
    setSuccessData(data)
    setMode("success")
    setHistoryKey((k) => k + 1)
    // 流水线：1.5s 后自动进入下一条（无下一条回工作台空态）
    jumpTimer.current = setTimeout(() => {
      router.push(data.nextEventId ? `/reports/review/${data.nextEventId}` : "/reports/review")
    }, 1500)
  }

  if (error && !detail) {
    return (
      <DashboardLayout title="报告处理" subtitle="审核工作台">
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <AlertCircle className="h-12 w-12 mb-4 text-warning" />
          <p className="mb-4">{error}</p>
          <Button variant="outline" onClick={loadDetail}>重试</Button>
        </div>
      </DashboardLayout>
    )
  }

  const riskCfg = detail ? getRiskConfig(detail.riskLevel) : null
  const RiskIcon = riskCfg?.icon
  const statusCfg = detail ? getReviewStatusConfig(detail.reviewStatus) : null
  const StatusIcon = statusCfg?.icon
  const isRevise = detail?.reviewStatus === "processed"
  const takeable = detail?.reviewStatus === "claimed" && isClaimStale(detail.claimedAt)

  return (
    <DashboardLayout title="报告处理" subtitle="审核工作台 · 逐份复核 AI 结论">
      <div className="space-y-4">
        {/* 顶部：返回 + 标题 + 状态 */}
        <div className="flex flex-wrap items-center gap-3">
          <Link
            href="/reports/review"
            className={buttonVariants({ variant: "ghost", size: "icon" })}
            aria-label="返回工作台"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold truncate">
              {detail?.title ?? "加载中..."}
            </h2>
            <p className="text-sm text-muted-foreground">
              报告编号: {detail?.id} · 分析时间: {detail?.generatedAt}
            </p>
          </div>
          {riskCfg && RiskIcon && (
            <Badge className={cn("border", riskCfg.twBadge)}>
              <RiskIcon className="h-3 w-3 mr-1" />
              {riskCfg.label}
            </Badge>
          )}
          {statusCfg && StatusIcon && (
            <Badge className={cn("border", statusCfg.twBadge)}>
              <StatusIcon
                className={cn(
                  "h-3 w-3 mr-1",
                  detail?.reviewStatus === "claimed" && "animate-spin",
                )}
              />
              {statusCfg.label}
            </Badge>
          )}
        </div>

        <div className="grid gap-4 lg:grid-cols-5">
          {/* 左侧：报告证据（可滚动） */}
          <div className="space-y-4 lg:col-span-3">
            {detail ? (
              <>
                {/* 风险四卡 */}
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <Card className={cn(riskCfg?.twBg, "border-0")}>
                    <CardContent className="flex items-center gap-3 p-4">
                      <div className={cn("rounded-lg p-2", riskCfg?.twBg)}>
                        <AlertTriangle className={cn("h-4 w-4", riskCfg?.twText)} />
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">风险等级</p>
                        <p className={cn("font-semibold", riskCfg?.twText)}>
                          {riskCfg?.label}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                  <Card className="border-0 bg-info/10">
                    <CardContent className="flex items-center gap-3 p-4">
                      <div className="rounded-lg p-2 bg-info/20">
                        <Zap className="h-4 w-4 text-info" />
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">攻击类型</p>
                        <p className="font-semibold text-info">{detail.attackType}</p>
                      </div>
                    </CardContent>
                  </Card>
                  <Card className="border-0 bg-success/10">
                    <CardContent className="flex items-center gap-3 p-4">
                      <div className="rounded-lg p-2 bg-success/20">
                        <Brain className="h-4 w-4 text-success" />
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">AI可信度</p>
                        <p className={cn("font-semibold", getConfidenceColor(detail.confidence))}>
                          {detail.confidence}%
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                  <Card className="border-0 bg-warning/10">
                    <CardContent className="flex items-center gap-3 p-4">
                      <div className="rounded-lg p-2 bg-warning/20">
                        <Target className="h-4 w-4 text-warning" />
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">风险分数</p>
                        <p className="font-semibold text-warning">{detail.riskScore}</p>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* AI 分析 */}
                <Card>
                  <CardHeader className="flex flex-row items-center gap-2">
                    <Brain className="h-5 w-5 text-primary" />
                    <CardTitle className="text-base">AI 分析</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <h3 className="mb-2 font-semibold">分析总结</h3>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {detail.summary || "暂无分析总结"}
                      </p>
                    </div>
                    {detail.reasoning?.length > 0 && (
                      <div>
                        <h3 className="mb-2 font-semibold">原因分析</h3>
                        <ul className="space-y-2">
                          {detail.reasoning.map((item, index) => (
                            <li
                              key={index}
                              className="flex items-start gap-2 text-sm text-muted-foreground"
                            >
                              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                              {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {detail.recommendations?.length > 0 && (
                      <div>
                        <h3 className="mb-2 font-semibold">AI 处置建议</h3>
                        <ul className="space-y-2">
                          {detail.recommendations.map((item, index) => (
                            <li
                              key={index}
                              className="flex items-start gap-2 text-sm text-muted-foreground"
                            >
                              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                              {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* 原始风险数据 */}
                <Card>
                  <CardHeader className="flex flex-row items-center gap-2">
                    <FileText className="h-5 w-5 text-primary" />
                    <CardTitle className="text-base">原始风险数据</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      <InfoItem label="源 IP" value={detail.originalRiskData.ip} icon={<Globe className="h-4 w-4 text-muted-foreground" />} mono />
                      <InfoItem label="请求路径" value={detail.originalRiskData.path} icon={<Route className="h-4 w-4 text-muted-foreground" />} mono />
                      <InfoItem label="日志时间" value={detail.originalRiskData.log_timestamp} icon={<Clock className="h-4 w-4 text-muted-foreground" />} mono />
                      <InfoItem label="User Agent" value={detail.originalRiskData.user_agent} icon={<Shield className="h-4 w-4 text-muted-foreground" />} mono />
                      <InfoItem
                        label="状态码"
                        value={String(detail.originalRiskData.status || "-")}
                        icon={<Zap className="h-4 w-4 text-muted-foreground" />}
                      />
                      <InfoItem label="事件 ID" value={detail.originalRiskData.event_id} icon={<FileText className="h-4 w-4 text-muted-foreground" />} mono />
                    </div>
                    <div className="mt-4">
                      <h4 className="mb-2 text-sm font-medium">原始日志</h4>
                      <div className="rounded-lg border border-border bg-muted/50 p-4">
                        <pre className="whitespace-pre-wrap break-all font-mono text-xs text-muted-foreground">
                          {detail.originalRiskData.original_log || "暂无原始日志"}
                        </pre>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* 审核历史时间线 */}
                <Card>
                  <CardHeader className="flex flex-row items-center gap-2">
                    <History className="h-5 w-5 text-primary" />
                    <CardTitle className="text-base">审核历史</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ReviewHistoryTimeline eventId={detail.id} refreshKey={historyKey} />
                  </CardContent>
                </Card>
              </>
            ) : (
              <Card>
                <CardContent className="flex items-center justify-center py-16">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </CardContent>
              </Card>
            )}
          </div>

          {/* 右侧：sticky 审核表单 */}
          <div className="lg:col-span-2">
            <div className="space-y-4 lg:sticky lg:top-6">
              {mode === "loading" && (
                <Card>
                  <CardContent className="flex items-center justify-center py-16">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  </CardContent>
                </Card>
              )}

              {mode === "claim-gate" && detail && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Hand className="h-5 w-5 text-primary" />
                      {takeable ? "他人认领已超时，可接管" : "开始处理"}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      {takeable
                        ? `该报告此前被 ${detail.claimedBy ?? "他人"} 认领超过 30 分钟未完成，你可以接管处理。`
                        : "认领后他人不可重复处理（30 分钟超时后可接管）；认领是轻量协作锁，不改变报告内容。"}
                    </p>
                    <Button className="w-full gap-2" onClick={handleClaim} disabled={claiming}>
                      {claiming ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Hand className="h-4 w-4" />
                      )}
                      {claiming ? "认领中..." : takeable ? "接管并处理" : "开始处理（认领）"}
                    </Button>
                  </CardContent>
                </Card>
              )}

              {mode === "locked" && detail && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <User className="h-5 w-5 text-info" />
                      他人处理中
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-sm text-muted-foreground">
                      <span className="font-medium text-foreground">
                        {detail.claimedBy ?? "其他管理员"}
                      </span>{" "}
                      正在处理该报告（30 分钟超时后可接管），请稍后再来或查看其他报告。
                    </p>
                    <Link
                      href="/reports/review"
                      className={cn(buttonVariants({ variant: "outline" }), "w-full")}
                    >
                      返回工作台
                    </Link>
                  </CardContent>
                </Card>
              )}

              {mode === "form" && detail && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">
                      {isRevise ? "重新审核（改判）" : "提交审核结论"}
                    </CardTitle>
                    {isRevise && detail.review && (
                      <p className="text-xs text-muted-foreground">
                        当前结论：{detail.review.verdictLabel} ·{" "}
                        {detail.review.categoryLabel} ·{" "}
                        {detail.review.reviewerDisplayName ?? "未知用户"}
                      </p>
                    )}
                  </CardHeader>
                  <CardContent>
                    <ReviewForm
                      key={detail.id}
                      eventId={detail.id}
                      initial={
                        detail.review
                          ? {
                              verdict: detail.review.verdict,
                              category: detail.review.category,
                              actions: detail.review.actions,
                              comment: detail.review.comment,
                            }
                          : null
                      }
                      onSuccess={handleReviewSuccess}
                    />
                  </CardContent>
                </Card>
              )}

              {mode === "success" && successData && (
                <Card className="border-success/30">
                  <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
                    <CheckCircle2 className="h-12 w-12 text-success" />
                    <p className="font-semibold">
                      {successData.review.changeType === "revised" ? "已改判" : "审核完成"}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {successData.review.verdictLabel} ·{" "}
                      {successData.review.categoryLabel}
                    </p>
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      {successData.nextEventId
                        ? "正在进入下一条待处理报告..."
                        : "队列已清空，正在返回工作台..."}
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}

function InfoItem({
  label,
  value,
  icon,
  mono,
}: {
  label: string
  value: string
  icon: React.ReactNode
  mono?: boolean
}) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="mb-1 flex items-center gap-2">
        {icon}
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p className={cn("truncate text-sm", mono && "font-mono")} title={value}>
        {value || "-"}
      </p>
    </div>
  )
}
