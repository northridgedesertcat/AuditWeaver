/**
 * 报告审核枚举字典（与后端 reports/serializers.py 的 code 对齐，标签各自维护）
 * 参照 lib/risk-level.ts 的单一数据源风格，禁止在页面分散硬编码。
 */
import { CheckCircle2, Clock, Loader2, type LucideIcon } from "lucide-react"

/** 报告处理状态三态 */
export const REVIEW_STATUS_CONFIG = {
  pending: {
    label: "待处理",
    icon: Clock,
    twText: "text-warning",
    twBadge: "bg-warning/20 text-warning border-warning/30",
  },
  claimed: {
    label: "处理中",
    icon: Loader2,
    twText: "text-info",
    twBadge: "bg-info/20 text-info border-info/30",
  },
  processed: {
    label: "已处理",
    icon: CheckCircle2,
    twText: "text-success",
    twBadge: "bg-success/20 text-success border-success/30",
  },
} as const

export type ReviewStatusKey = keyof typeof REVIEW_STATUS_CONFIG

/** 容错获取处理状态配置（未知值 fallback 到 pending） */
export function getReviewStatusConfig(status: unknown) {
  const key = String(status ?? "").trim()
  if (key in REVIEW_STATUS_CONFIG) {
    return REVIEW_STATUS_CONFIG[key as ReviewStatusKey]
  }
  return REVIEW_STATUS_CONFIG.pending
}

/** 报告正确性（四档） */
export const VERDICT_OPTIONS = [
  {
    value: "correct",
    label: "报告正确",
    description: "AI 的攻击定性与风险等级符合实际",
  },
  {
    value: "false_positive",
    label: "误报",
    description: "正常流量，不应产生告警",
  },
  {
    value: "partially_correct",
    label: "部分正确",
    description: "方向对但类型/等级有偏差",
  },
  {
    value: "uncertain",
    label: "无法判定",
    description: "证据不足，暂不能下结论",
  },
] as const

/** 实际情况（六档） */
export const CATEGORY_OPTIONS = [
  { value: "real_attack", label: "真实攻击" },
  { value: "scanner_probe", label: "扫描探测" },
  { value: "normal_business", label: "正常业务" },
  { value: "rule_misfire", label: "规则误报" },
  { value: "ai_misjudgment", label: "AI误判" },
  { value: "other", label: "其他" },
] as const

/** 处置动作（多选七项） */
export const ACTION_OPTIONS = [
  { value: "ignored", label: "忽略/关闭" },
  { value: "observed", label: "持续观察" },
  { value: "ip_blocked", label: "已封禁 IP" },
  { value: "waf_rule_added", label: "已加 WAF/检测规则" },
  { value: "incident_created", label: "已转处置工单" },
  { value: "notified", label: "已通知相关方" },
  { value: "other", label: "其他" },
] as const

/** uncertain 软校验允许的动作集合（与后端一致） */
export const UNCERTAIN_ALLOWED_ACTIONS = new Set(["observed", "ignored", "other"])

export function getVerdictLabel(code: string): string {
  return VERDICT_OPTIONS.find((o) => o.value === code)?.label ?? code
}

export function getCategoryLabel(code: string): string {
  return CATEGORY_OPTIONS.find((o) => o.value === code)?.label ?? code
}

export function getActionLabel(code: string): string {
  return ACTION_OPTIONS.find((o) => o.value === code)?.label ?? code
}

/** 认领超时时长（与后端 CLAIM_TTL 一致：30 分钟惰性过期） */
export const CLAIM_TTL_MS = 30 * 60 * 1000

/** 解析后端本地时间字符串 "YYYY-MM-DD HH:MM:SS"（补 T 分隔符保证跨浏览器解析） */
export function parseLocalDateTime(s: string | null | undefined): Date | null {
  if (!s) return null
  const d = new Date(s.replace(" ", "T"))
  return isNaN(d.getTime()) ? null : d
}

/** 认领是否已超过 30 分钟（可接管） */
export function isClaimStale(claimedAt: string | null | undefined): boolean {
  const d = parseLocalDateTime(claimedAt)
  if (!d) return false
  return Date.now() - d.getTime() > CLAIM_TTL_MS
}
