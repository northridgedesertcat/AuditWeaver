import {
  AlertOctagon,
  AlertTriangle,
  AlertCircle,
  Shield,
  CheckCircle,
  type LucideIcon,
} from "lucide-react"

/**
 * 风险等级单一数据源
 *
 * 颜色与后端 threat-distribution 接口返回的 color 字段保持一致:
 *   Critical 红  oklch(0.5 0.25 25)
 *   High     橙  oklch(0.65 0.2 60)
 *   Medium   黄  oklch(0.75 0.15 95)
 *   Low      绿  oklch(0.75 0.12 145)
 *   Normal   灰  oklch(0.7 0.05 260)
 *
 * 各 UI 入口(威胁分布图 / 最近告警 / 分析报告列表 / 报告详情)
 * 必须引用本常量,禁止再分散硬编码颜色映射。
 */
export interface RiskLevelConfig {
  /** 中文标签 */
  label: string
  /** 与后端一致的 oklch 颜色,供图表直接消费 */
  color: string
  /** Tailwind 文字颜色类 */
  twText: string
  /** Tailwind 浅底色类 */
  twBg: string
  /** Tailwind 徽章类 */
  twBadge: string
  /** 配套图标 */
  icon: LucideIcon
}

export const RISK_LEVEL_CONFIG = {
  critical: {
    label: "严重",
    color: "oklch(0.5 0.25 25)",
    twText: "text-critical",
    twBg: "bg-critical/10",
    twBadge: "bg-critical/20 text-critical border-critical/30",
    icon: AlertOctagon,
  },
  high: {
    label: "高危",
    color: "oklch(0.65 0.2 60)",
    twText: "text-high",
    twBg: "bg-high/10",
    twBadge: "bg-high/20 text-high border-high/30",
    icon: AlertTriangle,
  },
  medium: {
    label: "中危",
    color: "oklch(0.75 0.15 95)",
    twText: "text-medium",
    twBg: "bg-medium/10",
    twBadge: "bg-medium/20 text-medium border-medium/30",
    icon: AlertCircle,
  },
  low: {
    label: "低危",
    color: "oklch(0.75 0.12 145)",
    twText: "text-success",
    twBg: "bg-success/10",
    twBadge: "bg-success/20 text-success border-success/30",
    icon: Shield,
  },
  normal: {
    label: "正常",
    color: "oklch(0.7 0.05 260)",
    twText: "text-muted-foreground",
    twBg: "bg-muted",
    twBadge: "bg-muted text-muted-foreground border-border",
    icon: CheckCircle,
  },
} as const satisfies Record<string, RiskLevelConfig>

export type RiskLevelKey = keyof typeof RISK_LEVEL_CONFIG

/** 威胁等级分布图的固定顺序(严重 → 正常) */
export const RISK_LEVEL_ORDER: RiskLevelKey[] = [
  "critical",
  "high",
  "medium",
  "low",
  "normal",
]

/** 后端 threat-distribution 接口返回的大写键到本地小写键的映射 */
const UPPER_TO_LOWER: Record<string, RiskLevelKey> = {
  CRITICAL: "critical",
  HIGH: "high",
  MEDIUM: "medium",
  LOW: "low",
  NORMAL: "normal",
  Critical: "critical",
  High: "high",
  Medium: "medium",
  Low: "low",
  Normal: "normal",
}

/**
 * 容错获取风险等级配置:
 * - 兼容大小写(Critical / critical / CRITICAL)
 * - 兼容中文(严重 / 高危 / 中危 / 低危 / 正常)
 * - 兼容空值 / 未知值,fallback 到 normal
 */
export function getRiskConfig(level: unknown): RiskLevelConfig {
  const key = String(level ?? "").trim()
  if (!key) return RISK_LEVEL_CONFIG.normal

  const lower = key.toLowerCase()
  if (lower in RISK_LEVEL_CONFIG) {
    return RISK_LEVEL_CONFIG[lower as RiskLevelKey]
  }
  if (key in UPPER_TO_LOWER) {
    return RISK_LEVEL_CONFIG[UPPER_TO_LOWER[key]]
  }
  switch (key) {
    case "严重":
      return RISK_LEVEL_CONFIG.critical
    case "高危":
      return RISK_LEVEL_CONFIG.high
    case "中危":
      return RISK_LEVEL_CONFIG.medium
    case "低危":
      return RISK_LEVEL_CONFIG.low
    case "正常":
      return RISK_LEVEL_CONFIG.normal
    default:
      return RISK_LEVEL_CONFIG.normal
  }
}

/**
 * AI 置信度颜色阈值(统一收口):
 *   >= 90  success(绿)
 *   >= 75  warning(黄)
 *   其它   muted-foreground(灰)
 */
export function getConfidenceColor(confidence: number): string {
  if (confidence >= 90) return "text-success"
  if (confidence >= 75) return "text-warning"
  return "text-muted-foreground"
}
