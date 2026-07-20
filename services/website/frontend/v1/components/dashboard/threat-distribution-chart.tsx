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

interface ThreatLevelData {
  name: string
  value: number
  color: string
}

// 五种风险等级（来源: dify_response.data.outputs.structured_output.risk_level）
// 颜色与后端保持一致
const FALLBACK_DATA: ThreatLevelData[] = [
  { name: "严重", value: 0, color: "oklch(0.5 0.25 25)" },      // Critical - 红色
  { name: "高危", value: 0, color: "oklch(0.65 0.2 60)" },     // High - 橙色
  { name: "中危", value: 0, color: "oklch(0.75 0.15 95)" },    // Medium - 黄色
  { name: "低危", value: 0, color: "oklch(0.75 0.12 145)" },   // Low - 绿色
  { name: "正常", value: 0, color: "oklch(0.7 0.05 260)" },     // Normal - 灰色
]

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
        // 转换为 recharts 需要的数组格式
        const order = ["Critical", "High", "Medium", "Low", "Normal"]
        const chartData: ThreatLevelData[] = order
          .map((key) => result.data?.[key])
          .filter(Boolean)

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
