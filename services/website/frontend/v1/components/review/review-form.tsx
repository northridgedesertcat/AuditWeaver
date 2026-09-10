"use client"

/**
 * 审核结论表单：verdict 四选一 / category 六选一 / actions 多选 / comment 必填。
 * 400 字段级错误就地展示；409（他人认领中）顶部警示条；Ctrl+Enter 提交。
 */
import { useMemo, useState } from "react"
import { apiFetch } from "@/lib/api/client"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { AlertTriangle, Check, Loader2, Send } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  ACTION_OPTIONS,
  CATEGORY_OPTIONS,
  UNCERTAIN_ALLOWED_ACTIONS,
  VERDICT_OPTIONS,
} from "@/lib/review-options"

export interface ReviewInitialValue {
  verdict: string
  category: string
  actions: string[]
  comment: string
}

export interface ReviewSubmitResult {
  eventId: string
  reviewStatus: string
  nextEventId: string | null
  review: {
    verdict: string
    verdictLabel: string
    categoryLabel: string
    actionLabels: string[]
    comment: string
    changeType: string
  }
}

interface ReviewFormProps {
  eventId: string
  /** 改判时预填当前结论 */
  initial?: ReviewInitialValue | null
  submitting?: boolean
  onSubmittingChange?: (v: boolean) => void
  onSuccess: (data: ReviewSubmitResult) => void
}

type FieldErrors = Partial<Record<"verdict" | "category" | "actions" | "comment" | "detail", string>>

export function ReviewForm({
  eventId,
  initial,
  onSubmittingChange,
  onSuccess,
}: ReviewFormProps) {
  const [verdict, setVerdict] = useState<string>(initial?.verdict ?? "")
  const [category, setCategory] = useState<string>(initial?.category ?? "")
  const [actions, setActions] = useState<string[]>(initial?.actions ?? [])
  const [comment, setComment] = useState<string>(initial?.comment ?? "")
  const [errors, setErrors] = useState<FieldErrors>({})
  const [conflict, setConflict] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // 软校验提示：无法判定时不允许确定性处置动作（与后端一致）
  const uncertainInvalid = useMemo(() => {
    if (verdict !== "uncertain") return false
    return actions.some((a) => !UNCERTAIN_ALLOWED_ACTIONS.has(a))
  }, [verdict, actions])

  const commentInvalid = comment.trim().length > 0 && comment.trim().length < 5
  const canSubmit = verdict && category && comment.trim().length >= 5 && !uncertainInvalid

  const toggleAction = (code: string) => {
    setActions((prev) =>
      prev.includes(code) ? prev.filter((a) => a !== code) : [...prev, code],
    )
  }

  const handleSubmit = async () => {
    if (submitting || !canSubmit) return
    setSubmitting(true)
    onSubmittingChange?.(true)
    setErrors({})
    setConflict(null)
    try {
      const resp = await apiFetch(`/reports/${eventId}/review/`, {
        method: "POST",
        body: JSON.stringify({ verdict, category, actions, comment }),
      })
      if (resp.ok) {
        onSuccess(await resp.json())
        return
      }
      const data = await resp.json().catch(() => null)
      if (resp.status === 409) {
        setConflict(data?.error || "报告已被他人认领处理中")
      } else if (data && typeof data === "object") {
        const next: FieldErrors = {}
        for (const [key, value] of Object.entries(data)) {
          next[key as keyof FieldErrors] = Array.isArray(value)
            ? String(value[0])
            : String(value)
        }
        setErrors(next)
      } else {
        setErrors({ detail: `提交失败：HTTP ${resp.status}` })
      }
    } catch {
      setErrors({ detail: "网络连接失败，请检查后端服务是否运行" })
    } finally {
      setSubmitting(false)
      onSubmittingChange?.(false)
    }
  }

  return (
    <div className="space-y-5">
      {conflict && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{conflict}</span>
        </div>
      )}
      {errors.detail && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errors.detail}</span>
        </div>
      )}

      {/* 报告正确性：四选一 */}
      <div className="space-y-2">
        <Label>报告正确性</Label>
        <div className="grid grid-cols-2 gap-2">
          {VERDICT_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setVerdict(option.value)}
              className={cn(
                "rounded-lg border p-3 text-left transition-colors",
                verdict === option.value
                  ? "border-primary bg-primary/10"
                  : "border-border hover:bg-muted/50",
              )}
            >
              <span className="flex items-center gap-1.5 text-sm font-medium">
                {verdict === option.value && (
                  <Check className="h-3.5 w-3.5 text-primary" />
                )}
                {option.label}
              </span>
              <span className="mt-1 block text-xs text-muted-foreground">
                {option.description}
              </span>
            </button>
          ))}
        </div>
        {errors.verdict && <p className="text-xs text-destructive">{errors.verdict}</p>}
      </div>

      {/* 实际情况：六选一 */}
      <div className="space-y-2">
        <Label>实际情况</Label>
        <Select value={category} onValueChange={(value) => setCategory(value ?? "")}>
          <SelectTrigger>
            <SelectValue placeholder="选择实际情况" />
          </SelectTrigger>
          <SelectContent>
            {CATEGORY_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {errors.category && <p className="text-xs text-destructive">{errors.category}</p>}
      </div>

      {/* 处置动作：多选 */}
      <div className="space-y-2">
        <Label>处置动作（可多选）</Label>
        <div className="flex flex-wrap gap-2">
          {ACTION_OPTIONS.map((option) => {
            const active = actions.includes(option.value)
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => toggleAction(option.value)}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                  active
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:bg-muted/50",
                )}
              >
                {active && <Check className="h-3 w-3" />}
                {option.label}
              </button>
            )
          })}
        </div>
        {uncertainInvalid && (
          <p className="text-xs text-destructive">
            无法判定时处置动作仅允许：持续观察/忽略/其他
          </p>
        )}
        {errors.actions && !uncertainInvalid && (
          <p className="text-xs text-destructive">{errors.actions}</p>
        )}
      </div>

      {/* 处理说明 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="review-comment">处理说明</Label>
          <span
            className={cn(
              "text-xs",
              commentInvalid ? "text-destructive" : "text-muted-foreground",
            )}
          >
            {comment.trim().length}/∞（至少 5 个字符）
          </span>
        </div>
        <Textarea
          id="review-comment"
          placeholder="记录实际情况、处置依据与后续动作，便于回溯审计..."
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
              handleSubmit()
            }
          }}
          rows={5}
        />
        {commentInvalid && (
          <p className="text-xs text-destructive">处理说明至少需要 5 个字符</p>
        )}
        {errors.comment && <p className="text-xs text-destructive">{errors.comment}</p>}
      </div>

      <Button
        className="w-full gap-2"
        onClick={handleSubmit}
        disabled={!canSubmit || submitting}
      >
        {submitting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
        {submitting ? "提交中..." : "提交审核结论"}
        <span className="ml-1 text-xs opacity-70">Ctrl+Enter</span>
      </Button>
    </div>
  )
}
