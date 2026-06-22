"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  ArrowLeft,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  Clock,
  Globe,
  Route,
  Brain,
  FileText,
  ExternalLink,
  Shield,
  Zap,
  Target,
  AlertOctagon,
  ChevronRight,
} from "lucide-react"
import { cn } from "@/lib/utils"

interface OriginalRiskData {
  event_id: string
  ip: string
  log_timestamp: string
  user_agent: string
  status: number
  path: string
}

interface ReportDetail {
  id: string
  title: string
  riskLevel: "critical" | "high" | "medium" | "low"
  attackType: string
  confidence: number
  riskScore: number
  generatedAt: string
  summary: string
  reasoning: string[]
  recommendations: string[]
  originalRiskData: OriginalRiskData
}

interface ReportDetailModalProps {
  reportId: string
  isOpen: boolean
  onClose: () => void
}

const riskConfig = {
  critical: {
    color: "text-critical",
    bg: "bg-critical/10",
    badge: "bg-critical/20 text-critical border-critical/30",
    label: "严重",
    icon: AlertOctagon,
  },
  high: {
    color: "text-warning",
    bg: "bg-warning/10",
    badge: "bg-warning/20 text-warning border-warning/30",
    label: "高危",
    icon: AlertTriangle,
  },
  medium: {
    color: "text-info",
    bg: "bg-info/10",
    badge: "bg-info/20 text-info border-info/30",
    label: "中危",
    icon: AlertCircle,
  },
  low: {
    color: "text-success",
    bg: "bg-success/10",
    badge: "bg-success/20 text-success border-success/30",
    label: "低危",
    icon: CheckCircle,
  },
}

export function ReportDetailModal({ reportId, isOpen, onClose }: ReportDetailModalProps) {
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<ReportDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchDetail = async () => {
    setLoading(true)
    setError(null)
    setDetail(null)
    const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'
    try {
      const response = await fetch(`${apiBase}/api/v1/reports/${reportId}/`)
      if (response.ok) {
        const data = await response.json()
        setDetail(data)
      } else {
        const errorData = await response.json().catch(() => null)
        setError(errorData?.error || `HTTP错误: ${response.status}`)
      }
    } catch (error) {
      console.error("Failed to fetch report detail:", error)
      setError("网络连接失败，请检查后端服务是否运行")
    }
    setLoading(false)
  }

  useEffect(() => {
    if (isOpen && reportId) {
      fetchDetail()
    }
  }, [isOpen, reportId])

  if (!isOpen) return null

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
        <div className="relative w-full max-w-5xl max-h-[90vh] overflow-hidden rounded-xl border border-border bg-background shadow-2xl">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
        <div className="relative w-full max-w-5xl max-h-[90vh] overflow-hidden rounded-xl border border-border bg-background shadow-2xl">
          <div className="flex flex-col items-center justify-center h-64 p-8">
            <AlertCircle className="h-12 w-12 text-warning mb-4" />
            <p className="text-muted-foreground mb-2">{error || "无法加载报告详情"}</p>
            <Button onClick={fetchDetail} variant="outline" size="sm">
              重试
            </Button>
          </div>
        </div>
      </div>
    )
  }

  const riskCfg = riskConfig[detail.riskLevel]
  const RiskIcon = riskCfg.icon

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative w-full max-w-5xl max-h-[90vh] overflow-hidden rounded-xl border border-border bg-background shadow-2xl">
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={onClose}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div>
              <h2 className="text-lg font-semibold">{detail.title}</h2>
              <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                <span>报告编号: {detail.id}</span>
                <span>生成时间: {detail.generatedAt}</span>
              </div>
            </div>
          </div>
          <Badge className={cn("border", riskCfg.badge)}>
            <RiskIcon className="h-3 w-3 mr-1" />
            {riskCfg.label}
          </Badge>
        </div>

        <div className="overflow-y-auto max-h-[calc(90vh-72px)]">
          <div className="grid gap-4 p-6 md:grid-cols-2 lg:grid-cols-4">
            <Card className={cn(riskCfg.bg, "border-0")}>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className={cn("rounded-lg p-2", riskCfg.bg)}>
                    <AlertTriangle className={cn("h-4 w-4", riskCfg.color)} />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">风险等级</p>
                    <p className={cn("font-semibold", riskCfg.color)}>{riskCfg.label}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 bg-info/10">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg p-2 bg-info/20">
                    <Zap className="h-4 w-4 text-info" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">攻击类型</p>
                    <p className="font-semibold text-info">{detail.attackType}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 bg-success/10">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg p-2 bg-success/20">
                    <Brain className="h-4 w-4 text-success" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">AI可信度</p>
                    <p className={cn("font-semibold", detail.confidence >= 90 ? "text-success" : detail.confidence >= 70 ? "text-info" : "text-warning")}>
                      {detail.confidence}%
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 bg-warning/10">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg p-2 bg-warning/20">
                    <Target className="h-4 w-4 text-warning" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">风险分数</p>
                    <p className="font-semibold text-warning">{detail.riskScore}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="px-6 pb-6">
            <Card>
              <CardHeader className="flex flex-row items-center gap-2">
                <Brain className="h-5 w-5 text-primary" />
                <CardTitle className="text-base">AI Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  <div>
                    <h3 className="mt-4 mb-2 text-lg font-semibold text-foreground">分析总结</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {detail.summary || "暂无分析总结"}
                    </p>
                  </div>
                  <div>
                    <h3 className="mt-4 mb-2 text-lg font-semibold text-foreground">原因分析</h3>
                    <ul className="space-y-2">
                      {detail.reasoning.map((item, index) => (
                        <li key={index} className="flex items-start gap-2 text-sm text-muted-foreground">
                          <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h3 className="mt-4 mb-2 text-lg font-semibold text-foreground">风险评估</h3>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-lg border border-border p-4">
                        <p className="text-xs text-muted-foreground mb-1">风险等级</p>
                        <p className={cn("font-semibold", riskCfg.color)}>{riskCfg.label}</p>
                      </div>
                      <div className="rounded-lg border border-border p-4">
                        <p className="text-xs text-muted-foreground mb-1">风险分数</p>
                        <p className="font-semibold text-warning">{detail.riskScore}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="px-6 pb-6">
            <Card>
              <CardHeader className="flex flex-row items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                <CardTitle className="text-base">原始风险数据</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  <div className="rounded-lg border border-border p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Globe className="h-4 w-4 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">事件ID</span>
                    </div>
                    <p className="font-mono text-sm">{detail.originalRiskData.event_id || "-"}</p>
                  </div>
                  <div className="rounded-lg border border-border p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Globe className="h-4 w-4 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">IP地址</span>
                    </div>
                    <p className="font-mono text-sm">{detail.originalRiskData.ip || "-"}</p>
                  </div>
                  <div className="rounded-lg border border-border p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Clock className="h-4 w-4 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">日志时间</span>
                    </div>
                    <p className="font-mono text-sm">{detail.originalRiskData.log_timestamp || "-"}</p>
                  </div>
                  <div className="rounded-lg border border-border p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Shield className="h-4 w-4 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">User Agent</span>
                    </div>
                    <p className="font-mono text-sm text-xs truncate max-w-full">{detail.originalRiskData.user_agent || "-"}</p>
                  </div>
                  <div className="rounded-lg border border-border p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Zap className="h-4 w-4 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">状态码</span>
                    </div>
                    <p className={cn("font-semibold", detail.originalRiskData.status >= 500 ? "text-destructive" : detail.originalRiskData.status >= 400 ? "text-warning" : "text-success")}>
                      {detail.originalRiskData.status || "-"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-border p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Route className="h-4 w-4 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">请求路径</span>
                    </div>
                    <p className="font-mono text-sm truncate">{detail.originalRiskData.path || "-"}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="px-6 pb-6">
            <Card>
              <CardHeader className="flex flex-row items-center gap-2">
                <Shield className="h-5 w-5 text-primary" />
                <CardTitle className="text-base">AI处置建议</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Zap className="h-4 w-4 text-primary" />
                    <h4 className="font-medium text-primary">处置建议</h4>
                  </div>
                  <ul className="space-y-2">
                    {detail.recommendations.map((recommendation, index) => (
                      <li key={index} className="flex items-start gap-2 text-sm text-muted-foreground">
                        <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                        {recommendation}
                      </li>
                    ))}
                  </ul>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}