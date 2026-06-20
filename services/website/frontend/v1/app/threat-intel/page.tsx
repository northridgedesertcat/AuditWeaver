"use client"

import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Input } from "@/components/ui/input"
import {
  Globe,
  Shield,
  AlertTriangle,
  Search,
  ExternalLink,
  MapPin,
  Clock,
  Target,
  Database,
  FileText,
  TrendingUp,
  Eye,
} from "lucide-react"
import { cn } from "@/lib/utils"

const threatFeeds = [
  {
    id: "feed-001",
    name: "AlienVault OTX",
    type: "开源情报",
    status: "active",
    lastUpdate: "5 分钟前",
    indicators: 125847,
  },
  {
    id: "feed-002",
    name: "VirusTotal",
    type: "恶意软件",
    status: "active",
    lastUpdate: "10 分钟前",
    indicators: 89456,
  },
  {
    id: "feed-003",
    name: "AbuseIPDB",
    type: "恶意 IP",
    status: "active",
    lastUpdate: "15 分钟前",
    indicators: 456789,
  },
  {
    id: "feed-004",
    name: "PhishTank",
    type: "钓鱼网站",
    status: "active",
    lastUpdate: "30 分钟前",
    indicators: 34567,
  },
  {
    id: "feed-005",
    name: "内部威胁情报",
    type: "自定义",
    status: "active",
    lastUpdate: "1 小时前",
    indicators: 1234,
  },
]

const recentThreats = [
  {
    id: "threat-001",
    indicator: "185.234.12.45",
    type: "IP 地址",
    category: "C2 服务器",
    severity: "critical",
    source: "AlienVault OTX",
    firstSeen: "2024-01-15 10:00",
    lastSeen: "2024-01-15 14:32",
    country: "俄罗斯",
    tags: ["APT", "恶意软件"],
  },
  {
    id: "threat-002",
    indicator: "malware.evil-domain.com",
    type: "域名",
    category: "恶意软件分发",
    severity: "high",
    source: "VirusTotal",
    firstSeen: "2024-01-14 08:00",
    lastSeen: "2024-01-15 12:00",
    country: "乌克兰",
    tags: ["恶意软件", "下载器"],
  },
  {
    id: "threat-003",
    indicator: "phishing-bank-login.com",
    type: "域名",
    category: "钓鱼网站",
    severity: "high",
    source: "PhishTank",
    firstSeen: "2024-01-15 06:00",
    lastSeen: "2024-01-15 14:00",
    country: "美国",
    tags: ["钓鱼", "金融"],
  },
  {
    id: "threat-004",
    indicator: "d41d8cd98f00b204e9800998ecf8427e",
    type: "文件哈希",
    category: "勒索软件",
    severity: "critical",
    source: "VirusTotal",
    firstSeen: "2024-01-13 12:00",
    lastSeen: "2024-01-15 08:00",
    country: "未知",
    tags: ["勒索软件", "加密"],
  },
  {
    id: "threat-005",
    indicator: "10.0.0.45",
    type: "IP 地址",
    category: "内部威胁",
    severity: "medium",
    source: "内部威胁情报",
    firstSeen: "2024-01-15 13:00",
    lastSeen: "2024-01-15 14:15",
    country: "内部网络",
    tags: ["端口扫描", "侦察"],
  },
]

const threatStats = {
  totalIndicators: 707893,
  newToday: 1234,
  matchedAlerts: 47,
  activeFeeds: 5,
  criticalThreats: 12,
  highThreats: 28,
}

const severityConfig = {
  critical: { label: "严重", color: "bg-critical/20 text-critical" },
  high: { label: "高危", color: "bg-warning/20 text-warning" },
  medium: { label: "中危", color: "bg-info/20 text-info" },
  low: { label: "低危", color: "bg-success/20 text-success" },
}

export default function ThreatIntelPage() {
  return (
    <DashboardLayout
      title="威胁情报"
      subtitle="全球威胁情报收集与分析"
    >
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="indicators">威胁指标</TabsTrigger>
          <TabsTrigger value="feeds">情报源</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {/* Stats */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <Database className="h-8 w-8 text-primary" />
                  <div>
                    <p className="text-sm text-muted-foreground">总指标数</p>
                    <p className="text-2xl font-bold">{(threatStats.totalIndicators / 1000).toFixed(0)}K</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <TrendingUp className="h-8 w-8 text-success" />
                  <div>
                    <p className="text-sm text-muted-foreground">今日新增</p>
                    <p className="text-2xl font-bold">{threatStats.newToday}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <Target className="h-8 w-8 text-warning" />
                  <div>
                    <p className="text-sm text-muted-foreground">匹配告警</p>
                    <p className="text-2xl font-bold">{threatStats.matchedAlerts}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <Globe className="h-8 w-8 text-info" />
                  <div>
                    <p className="text-sm text-muted-foreground">活跃情报源</p>
                    <p className="text-2xl font-bold">{threatStats.activeFeeds}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="h-8 w-8 text-critical" />
                  <div>
                    <p className="text-sm text-muted-foreground">严重威胁</p>
                    <p className="text-2xl font-bold text-critical">{threatStats.criticalThreats}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <Shield className="h-8 w-8 text-warning" />
                  <div>
                    <p className="text-sm text-muted-foreground">高危威胁</p>
                    <p className="text-2xl font-bold text-warning">{threatStats.highThreats}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Recent Threats */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base font-medium">最近威胁</CardTitle>
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input placeholder="搜索威胁指标..." className="pl-9" />
              </div>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px]">
                <div className="space-y-3">
                  {recentThreats.map((threat) => {
                    const config = severityConfig[threat.severity as keyof typeof severityConfig]

                    return (
                      <div
                        key={threat.id}
                        className="flex items-start gap-4 rounded-lg border border-border p-4 transition-colors hover:bg-muted/50"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-2">
                            <Badge className={cn("text-xs", config.color)}>
                              {config.label}
                            </Badge>
                            <Badge variant="outline" className="text-xs">
                              {threat.type}
                            </Badge>
                            <Badge variant="outline" className="text-xs">
                              {threat.category}
                            </Badge>
                          </div>
                          <p className="font-mono text-sm font-medium">{threat.indicator}</p>
                          <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
                            <span className="flex items-center gap-1">
                              <FileText className="h-3 w-3" />
                              {threat.source}
                            </span>
                            <span className="flex items-center gap-1">
                              <MapPin className="h-3 w-3" />
                              {threat.country}
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              最后发现: {threat.lastSeen}
                            </span>
                          </div>
                          <div className="mt-2 flex gap-1 flex-wrap">
                            {threat.tags.map((tag) => (
                              <Badge key={tag} variant="secondary" className="text-xs">
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <ExternalLink className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="indicators" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-medium">威胁指标库</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-12 text-muted-foreground">
                <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>包含 707,893 个威胁指标</p>
                <p className="text-sm">使用搜索功能查找特定指标</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="feeds" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base font-medium">情报源管理</CardTitle>
              <Button>
                添加情报源
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {threatFeeds.map((feed) => (
                  <div
                    key={feed.id}
                    className="flex items-center justify-between rounded-lg border border-border p-4"
                  >
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center">
                        <Globe className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <p className="font-medium">{feed.name}</p>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>{feed.type}</span>
                          <span>|</span>
                          <span>更新于 {feed.lastUpdate}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className="font-medium">{feed.indicators.toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">指标数</p>
                      </div>
                      <Badge variant="outline" className="bg-success/20 text-success">
                        活跃
                      </Badge>
                      <Button variant="ghost" size="sm">
                        配置
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </DashboardLayout>
  )
}
