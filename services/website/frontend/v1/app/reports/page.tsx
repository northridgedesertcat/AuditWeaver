"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { apiFetch } from '@/lib/api/client'
import { DashboardLayout } from "@/components/layout"
import { StatCard, ReportDetailModal } from "@/components/dashboard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  FileText,
  AlertTriangle,
  AlertCircle,
  Clock,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  Eye,
  Globe,
  Route,
  Brain,
  Loader2,
  ClipboardCheck,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { formatRelative } from "@/lib/time"
import { getRiskConfig, getConfidenceColor } from "@/lib/risk-level"
import {
  getReviewStatusConfig,
  parseLocalDateTime,
  type ReviewStatusKey,
} from "@/lib/review-options"

interface Report {
  id: string
  title: string
  riskLevel: "critical" | "high" | "medium" | "low" | "normal"
  attackType: string
  sourceIp: string
  targetPath: string
  generatedAt: string
  aiConfidence: number
  reviewStatus: ReviewStatusKey
  reviewedBy: string | null
  claimedBy: string | null
}

interface ReportStats {
  total: number
  highRisk: number
  mediumRisk: number
  todayNew: number
  pendingReview: number
}

// 处理状态筛选下拉项（值与后端 review_status 对齐；徽标样式统一走 lib/review-options）
const reviewStatuses = [
  { value: "all", label: "全部状态" },
  { value: "pending", label: "待处理" },
  { value: "claimed", label: "处理中" },
  { value: "processed", label: "已处理" },
]

const attackTypes = [
  { value: "all", label: "全部类型" },
  { value: "sql_injection", label: "SQL注入" },
  { value: "xss", label: "XSS攻击" },
  { value: "ddos", label: "DDoS攻击" },
  { value: "brute_force", label: "暴力破解" },
  { value: "malware", label: "恶意软件" },
  { value: "phishing", label: "钓鱼攻击" },
  { value: "data_exfiltration", label: "数据泄露" },
  { value: "unauthorized_access", label: "未授权访问" },
]

const riskLevels = [
  { value: "all", label: "全部等级" },
  { value: "critical", label: "严重" },
  { value: "high", label: "高危" },
  { value: "medium", label: "中危" },
  { value: "low", label: "低危" },
  { value: "normal", label: "正常" },
]

const timeRanges = [
  { value: "today", label: "今天" },
  { value: "week", label: "最近7天" },
  { value: "month", label: "最近30天" },
  { value: "quarter", label: "最近3个月" },
  { value: "year", label: "最近1年" },
  { value: "all", label: "全部时间" },
]

export default function ReportsPage() {
  const router = useRouter()
  const [stats, setStats] = useState<ReportStats>({
    total: 0,
    highRisk: 0,
    mediumRisk: 0,
    todayNew: 0,
    pendingReview: 0,
  })
  const [reports, setReports] = useState<Report[]>([])
  const [totalReports, setTotalReports] = useState(0)
  const [loading, setLoading] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(5)
  const [filters, setFilters] = useState({
    timeRange: "all",
    riskLevel: "all",
    attackType: "all",
    reviewStatus: "all",
    keyword: "",
  })
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [selectedReportId, setSelectedReportId] = useState("")

  // 获取报告统计数据
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await apiFetch('/reports/stats/')
        if (response.ok) {
          const data = await response.json()
          setStats({
            total: data.total || 0,
            highRisk: data.highRisk || 0,
            mediumRisk: data.mediumRisk || 0,
            todayNew: data.todayNew || 0,
            pendingReview: data.pendingReview || 0,
          })
        }
      } catch (error) {
        console.error('获取报告统计失败:', error)
      }
    }

    fetchStats()
  }, [])

  // 获取报告列表数据
  useEffect(() => {
    const fetchReports = async () => {
      setLoading(true)
      try {
        // 构建查询参数
        const params = new URLSearchParams()
        params.append('page', currentPage.toString())
        params.append('size', pageSize.toString())
        if (filters.riskLevel !== 'all') {
          params.append('risk_level', filters.riskLevel)
        }
        if (filters.attackType !== 'all') {
          params.append('attack_type', filters.attackType)
        }
        if (filters.reviewStatus !== 'all') {
          params.append('review_status', filters.reviewStatus)
        }
        if (filters.keyword) {
          params.append('keyword', filters.keyword)
        }

        const response = await apiFetch(`/reports/list/?${params.toString()}`)
        if (response.ok) {
          const data = await response.json()
          setReports(data.data || [])
          setTotalReports(data.total || 0)
        }
      } catch (error) {
        console.error('获取报告列表失败:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchReports()
  }, [currentPage, pageSize, filters.riskLevel, filters.attackType, filters.reviewStatus, filters.keyword])

  // 分页 - 使用后端返回的总数
  const totalPages = Math.ceil(totalReports / pageSize)

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
    setCurrentPage(1) // 重置到第一页
  }

  const handleSearch = () => {
    setCurrentPage(1)
  }

  const handleViewDetails = (reportId: string) => {
    setSelectedReportId(reportId)
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setSelectedReportId("")
  }

  return (
    <DashboardLayout
      title="AI Security Reports"
      subtitle="AI安全分析报告中心"
    >
      <div className="space-y-6">
        {/* 统计卡片 */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          <StatCard
            title="总报告数"
            value={stats.total}
            iconName="file-text"
            iconColor="text-primary"
            description="累计生成"
          />
          <StatCard
            title="待处理报告"
            value={stats.pendingReview}
            iconName="clock"
            iconColor="text-warning"
            description="等待人工审核"
          />
          <StatCard
            title="高危报告"
            value={stats.highRisk}
            change="+3"
            changeType="negative"
            iconName="alert-triangle"
            iconColor="text-warning"
            description="需要关注"
          />
          <StatCard
            title="中危报告"
            value={stats.mediumRisk}
            change="-2"
            changeType="positive"
            iconName="alert-circle"
            iconColor="text-info"
            description="待处理"
          />
          <StatCard
            title="今日新增"
            value={stats.todayNew}
            change="+5"
            changeType="neutral"
            iconName="clock"
            iconColor="text-success"
            description="较昨日"
          />
        </div>

        {/* 筛选区域 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Filter className="h-4 w-4" />
              筛选条件
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              {/* 时间范围 */}
              <div className="space-y-2">
                <Label htmlFor="time-range">时间范围</Label>
                <Select
                  value={filters.timeRange}
                  onValueChange={(value) => handleFilterChange("timeRange", value ?? "all")}
                >
                  <SelectTrigger id="time-range">
                    <SelectValue placeholder="选择时间范围" />
                  </SelectTrigger>
                  <SelectContent>
                    {timeRanges.map((range) => (
                      <SelectItem key={range.value} value={range.value}>
                        {range.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* 风险等级 */}
              <div className="space-y-2">
                <Label htmlFor="risk-level">风险等级</Label>
                <Select
                  value={filters.riskLevel}
                  onValueChange={(value) => handleFilterChange("riskLevel", value ?? "all")}
                >
                  <SelectTrigger id="risk-level">
                    <SelectValue placeholder="选择风险等级" />
                  </SelectTrigger>
                  <SelectContent>
                    {riskLevels.map((level) => (
                      <SelectItem key={level.value} value={level.value}>
                        {level.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* 攻击类型 */}
              <div className="space-y-2">
                <Label htmlFor="attack-type">攻击类型</Label>
                <Select
                  value={filters.attackType}
                  onValueChange={(value) => handleFilterChange("attackType", value ?? "all")}
                >
                  <SelectTrigger id="attack-type">
                    <SelectValue placeholder="选择攻击类型" />
                  </SelectTrigger>
                  <SelectContent>
                    {attackTypes.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* 处理状态 */}
              <div className="space-y-2">
                <Label htmlFor="review-status">处理状态</Label>
                <Select
                  value={filters.reviewStatus}
                  onValueChange={(value) => handleFilterChange("reviewStatus", value ?? "all")}
                >
                  <SelectTrigger id="review-status">
                    <SelectValue placeholder="选择处理状态" />
                  </SelectTrigger>
                  <SelectContent>
                    {reviewStatuses.map((status) => (
                      <SelectItem key={status.value} value={status.value}>
                        {status.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* 关键字搜索 */}
              <div className="space-y-2">
                <Label htmlFor="keyword">关键字搜索</Label>
                <div className="flex gap-2">
                  <Input
                    id="keyword"
                    placeholder="搜索报告标题、IP或路径..."
                    value={filters.keyword}
                    onChange={(e) => handleFilterChange("keyword", e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  />
                  <Button onClick={handleSearch} size="icon" variant="secondary">
                    <Search className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 报告列表 */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">分析报告列表</CardTitle>
              <Badge variant="outline">
                共 {totalReports} 条记录
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : reports.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <FileText className="h-12 w-12 mb-4 opacity-50" />
                <p>暂无报告数据</p>
              </div>
            ) : (
              <div className="space-y-4">
                {reports.map((report) => {
                  const riskCfg = getRiskConfig(report.riskLevel)
                  const statusCfg = getReviewStatusConfig(report.reviewStatus)
                  const StatusIcon = statusCfg.icon
                  // 徽标文案：已处理 · 张三 / 张三处理中 / 待处理
                  const statusLabel =
                    report.reviewStatus === "processed"
                      ? `已处理${report.reviewedBy ? ` · ${report.reviewedBy}` : ""}`
                      : report.reviewStatus === "claimed"
                        ? `${report.claimedBy ?? ""}处理中`
                        : statusCfg.label
                  const genMs = parseLocalDateTime(report.generatedAt)?.getTime()

                  return (
                    <div
                      key={report.id}
                      className={cn(
                        "rounded-lg border p-4 transition-all hover:shadow-md",
                        riskCfg.twBg
                      )}
                    >
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        {/* 左侧信息 */}
                        <div className="flex-1 space-y-3">
                          {/* 标题和风险等级 */}
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold text-base">
                              {report.title}
                            </h3>
                            <Badge className={cn("border", riskCfg.twBadge)}>
                              {riskCfg.label}
                            </Badge>
                            <Badge className={cn("border", statusCfg.twBadge)}>
                              <StatusIcon className={cn(
                                "mr-1 h-3 w-3",
                                report.reviewStatus === "claimed" && "animate-spin"
                              )} />
                              {statusLabel}
                            </Badge>
                          </div>

                          {/* 详细信息 */}
                          <div className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2 lg:grid-cols-4">
                            <div className="flex items-center gap-2">
                              <AlertTriangle className="h-4 w-4 shrink-0" />
                              <span className="truncate">攻击类型: {report.attackType}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Globe className="h-4 w-4 shrink-0" />
                              <span className="truncate font-mono">来源: {report.sourceIp}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Route className="h-4 w-4 shrink-0" />
                              <span className="truncate">目标: {report.targetPath}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Brain className="h-4 w-4 shrink-0" />
                              <span className="truncate">
                                AI可信度:
                                <span className={cn(
                                  "ml-1 font-semibold",
                                  getConfidenceColor(report.aiConfidence)
                                )}>
                                  {report.aiConfidence}%
                                </span>
                              </span>
                            </div>
                          </div>

                          {/* 生成时间 */}
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Clock className="h-3.5 w-3.5" />
                            <span>生成时间: {genMs ? formatRelative(genMs) : report.generatedAt || "未知时间"}</span>
                          </div>
                        </div>

                        {/* 右侧操作按钮：pending/claimed → 去处理；processed → 查看详情（弹窗内可去改判） */}
                        <div className="flex items-center gap-2 lg:flex-col lg:items-end">
                          {report.reviewStatus === "processed" ? (
                            <Button
                              onClick={() => handleViewDetails(report.id)}
                              variant="outline"
                              size="sm"
                              className="gap-2"
                            >
                              <Eye className="h-4 w-4" />
                              查看详情
                            </Button>
                          ) : (
                            <Button
                              onClick={() => router.push(`/reports/review/${report.id}`)}
                              size="sm"
                              className="gap-2"
                            >
                              <ClipboardCheck className="h-4 w-4" />
                              去处理
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {/* 分页 */}
            {totalPages > 1 && (
              <div className="mt-6 flex items-center justify-between border-t pt-4">
                <div className="text-sm text-muted-foreground">
                  显示第 {(currentPage - 1) * pageSize + 1} - {Math.min(currentPage * pageSize, totalReports)} 条，共 {totalReports} 条
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    上一页
                  </Button>
                  <div className="flex items-center gap-1">
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                      <Button
                        key={page}
                        variant={currentPage === page ? "default" : "outline"}
                        size="sm"
                        onClick={() => setCurrentPage(page)}
                        className="h-8 w-8 p-0"
                      >
                        {page}
                      </Button>
                    ))}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                  >
                    下一页
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      <ReportDetailModal
        reportId={selectedReportId}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
    </DashboardLayout>
  )
}