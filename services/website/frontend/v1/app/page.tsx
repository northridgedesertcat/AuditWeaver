"use client"

import { useState, useEffect } from "react"
import { DashboardLayout } from "@/components/layout"
import {
  StatCard,
  LogVolumeChart,
  ThreatDistributionChart,
  RecentAlerts,
  SystemStatus,
  AIInsights,
} from "@/components/dashboard"

interface DashboardStats {
  logVolume: string
  attackLogs: string
  highSeverityAlerts: string
  riskIps: string
  totalLogs: string
  avgResponseTime: string
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({
    logVolume: "2.3M",
    attackLogs: "28",
    highSeverityAlerts: "174",
    riskIps: "12",
    totalLogs: "1,847",
    avgResponseTime: "1.2s",
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/v1/dashboard/stats/")
        const data = await response.json()
        setStats({
          logVolume: data.logVolume || "0",
          attackLogs: data.attackLogs || "0",
          highSeverityAlerts: data.highSeverityAlerts || "0",
          riskIps: data.riskIps || "0",
          totalLogs: data.totalLogs || "0",
          avgResponseTime: data.avgResponseTime || "0",
        })
      } catch (error) {
        console.error("Failed to fetch dashboard stats:", error)
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
    const interval = setInterval(fetchStats, 10000)

    return () => clearInterval(interval)
  }, [])

  return (
    <DashboardLayout
      title="执行概览"
      subtitle="实时安全态势监控与分析"
    >
      <div className="space-y-6">
        {/* Stats Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <StatCard
            title="今日日志量"
            value={loading ? "加载中..." : stats.logVolume}
            change="+12.5%"
            changeType="positive"
            iconName="file-text"
            description="较昨日"
          />
          <StatCard
            title="今日攻击日志数"
            value={loading ? "加载中..." : stats.attackLogs}
            change="+5"
            changeType="negative"
            iconName="alert-triangle"
            description="较1小时前"
          />
          <StatCard
            title="今日高危告警数"
            value={loading ? "加载中..." : stats.highSeverityAlerts}
            change="-8.2%"
            changeType="positive"
            iconName="shield"
            description="较昨日"
          />
          <StatCard
            title="风险IP数"
            value={loading ? "加载中..." : stats.riskIps}
            change="+3"
            changeType="negative"
            iconName="activity"
            description="待处理"
          />
          <StatCard
            title="总日志数"
            value={loading ? "加载中..." : stats.totalLogs}
            change="+156"
            changeType="positive"
            iconName="zap"
            description="今日完成"
          />
          <StatCard
            title="平均响应时间"
            value={loading ? "加载中..." : stats.avgResponseTime}
            change="-0.3s"
            changeType="positive"
            iconName="clock"
            description="较上周"
          />
        </div>

        {/* Charts Row */}
        <div className="grid gap-4 lg:grid-cols-3">
          <LogVolumeChart />
          <ThreatDistributionChart />
        </div>

        {/* AI Insights */}
        <AIInsights />

        {/* Alerts and Status */}
        <div className="grid gap-4 lg:grid-cols-2">
          <RecentAlerts />
          <SystemStatus />
        </div>
      </div>
    </DashboardLayout>
  )
}