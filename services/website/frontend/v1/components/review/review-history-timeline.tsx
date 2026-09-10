"use client"

/**
 * 审核历史时间线：调 GET /reports/{eventId}/review/history/，
 * 垂直时间线展示每次结论快照（首次审核/改判徽标 + 结论 + 处理人 + 时间）。
 */
import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api/client"
import { Badge } from "@/components/ui/badge"
import { History, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  getActionLabel,
  getCategoryLabel,
  getVerdictLabel,
} from "@/lib/review-options"

interface HistoryItem {
  changeType: "created" | "revised"
  verdict: string
  verdictLabel?: string
  category: string
  categoryLabel?: string
  actions: string[]
  comment: string
  reviewerDisplayName: string | null
  createdAt: string
}

interface ReviewHistoryTimelineProps {
  eventId: string
  /** 提交后自增以触发重新拉取 */
  refreshKey?: number
}

export function ReviewHistoryTimeline({
  eventId,
  refreshKey = 0,
}: ReviewHistoryTimelineProps) {
  const [loading, setLoading] = useState(true)
  const [items, setItems] = useState<HistoryItem[]>([])

  useEffect(() => {
    let cancelled = false
    const fetchHistory = async () => {
      setLoading(true)
      try {
        const resp = await apiFetch(`/reports/${eventId}/review/history/`)
        if (resp.ok && !cancelled) {
          const data = await resp.json()
          setItems(data.history || [])
        }
      } catch (error) {
        console.error("获取审核历史失败:", error)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchHistory()
    return () => {
      cancelled = true
    }
  }, [eventId, refreshKey])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
        暂无审核记录
      </div>
    )
  }

  return (
    <div className="space-y-0">
      {items.map((item, index) => (
        <div key={index} className="relative flex gap-3 pb-5 last:pb-0">
          {/* 时间线竖线与圆点 */}
          {index < items.length - 1 && (
            <span className="absolute left-[7px] top-4 h-full w-px bg-border" />
          )}
          <span
            className={cn(
              "relative mt-1.5 h-3.5 w-3.5 shrink-0 rounded-full border-2",
              item.changeType === "revised"
                ? "border-info bg-info/30"
                : "border-primary bg-primary/30",
            )}
          />
          <div className="flex-1 space-y-1.5 rounded-lg border border-border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                className={cn(
                  "border",
                  item.changeType === "revised"
                    ? "bg-info/20 text-info border-info/30"
                    : "bg-primary/10 text-primary border-primary/30",
                )}
              >
                {item.changeType === "revised" ? "改判" : "首次审核"}
              </Badge>
              <span className="text-sm font-medium">
                {getVerdictLabel(item.verdict)} · {getCategoryLabel(item.category)}
              </span>
            </div>
            {item.actions?.length > 0 && (
              <p className="text-xs text-muted-foreground">
                处置：
                {item.actions.map((a) => getActionLabel(a)).join("、")}
              </p>
            )}
            <p className="text-sm text-muted-foreground">{item.comment}</p>
            <p className="text-xs text-muted-foreground/70">
              {item.reviewerDisplayName ?? "未知用户"} · {item.createdAt}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}
