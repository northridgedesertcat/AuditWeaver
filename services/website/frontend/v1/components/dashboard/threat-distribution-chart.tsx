"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts"
import {
  RISK_LEVEL_CONFIG,
  RISK_LEVEL_ORDER,
  getRiskConfig,
} from "@/lib/risk-level"

interface ThreatLevelData {
  name: string
  value: number
  color: string
}

// 兜底数据:从单一数据源派生,保证颜色与其它组件永远一致
const FALLBACK_DATA: ThreatLevelData[] = RISK_LEVEL_ORDER.map((key) => ({
  name: RISK_LEVEL_CONFIG[key].label,
  value: 0,
  color: RISK_LEVEL_CONFIG[key].color,
}))

export function ThreatDistributionChart() {
  const [data, setData] = useState<ThreatLevelData[]>(FALLBACK_DATA)
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    const fetchDistribution = async () => {
      try {
        const response = await fetch(
          "http://localhost:8000/api/v1/dashboard/threat-distribution/?range=all"
        )
        const result = await response.json()

        // 后端返回结构: { data: { Critical: {name, value, color}, ... }, total }
        // 按 RISK_LEVEL_ORDER 顺序提取,并对缺失/异常的 color 用单一数据源兜底,
        // 防止后端 color 字段漂移导致与其它组件颜色不一致
        const chartData: ThreatLevelData[] = RISK_LEVEL_ORDER.map((key) => {
          // 兼容大写 Critical/High/... 与小写 critical/high/... 两种键
          const raw =
            result.data?.[key.charAt(0).toUpperCase() + key.slice(1)] ??
            result.data?.[key]
          if (!raw) return null
          const cfg = getRiskConfig(key)
          return {
            name: raw.name ?? cfg.label,
            value: Number(raw.value) || 0,
            color: cfg.color,
          }
        }).filter(Boolean) as ThreatLevelData[]

        if (chartData.length > 0) {
          setData(chartData)
        }
        setTotal(result.total ?? 0)
      } catch (error) {
        console.error("Failed to fetch threat distribution:", error)
        // 出错时保持默认全 0 数据
      } finally {
        setLoading(false)
      }
    }

    fetchDistribution()
    // 每 30 秒刷新一次
    const interval = setInterval(fetchDistribution, 30000)

    return () => clearInterval(interval)
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-medium">威胁等级分布</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] w-full">
          {loading ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              加载中...
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {data.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "oklch(0.18 0.02 260)",
                    border: "1px solid oklch(0.28 0.03 260)",
                    borderRadius: "8px",
                    color: "oklch(0.95 0.01 260)",
                  }}
                />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  formatter={(value) => (
                    <span style={{ color: "oklch(0.85 0.01 260)" }}>{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="mt-2 text-center text-xs text-muted-foreground">
          总计: <span className="font-medium text-foreground">{total}</span> 条分析报告
        </div>
      </CardContent>
    </Card>
  )
}
