"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { formatTimeOnly } from "@/lib/time"

interface TrendData {
  time: number
  logs: number
}

export function LogVolumeChart() {
  const [data, setData] = useState<TrendData[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchTrend = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/v1/logs/trend/")
        const result = await response.json()
        
        if (result.data && result.data.length > 0) {
          setData(result.data)
        } else {
          setData([])
        }
      } catch (error) {
        console.error("Failed to fetch log trend:", error)
        setData([])
      } finally {
        setLoading(false)
      }
    }

    fetchTrend()
    const interval = setInterval(fetchTrend, 30000)

    return () => clearInterval(interval)
  }, [])

  const maxLogs = data.length > 0 ? Math.max(...data.map(d => d.logs), 1) : 1

  return (
    <Card className="col-span-2">
      <CardHeader>
        <CardTitle className="text-base font-medium">日志量趋势</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] w-full">
          {loading ? (
            <div className="h-full flex items-center justify-center text-gray-500">
              加载中...
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={data}>
                <defs>
                  <linearGradient id="colorLogs" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="oklch(0.65 0.2 250)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="oklch(0.65 0.2 250)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.28 0.03 260)" />
                <XAxis
                  dataKey="time"
                  stroke="oklch(0.65 0.02 260)"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  interval={2}
                  tickFormatter={(value) => formatTimeOnly(value as number)}
                />
                <YAxis
                  stroke="oklch(0.65 0.02 260)"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => {
                    if (value >= 1000000) {
                      return `${(value / 1000000).toFixed(1)}M`
                    } else if (value >= 1000) {
                      return `${(value / 1000).toFixed(0)}K`
                    }
                    return value.toString()
                  }}
                  domain={[0, maxLogs * 1.2]}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "oklch(0.18 0.02 260)",
                    border: "1px solid oklch(0.28 0.03 260)",
                    borderRadius: "8px",
                    color: "oklch(0.95 0.01 260)",
                  }}
                  labelStyle={{ color: "oklch(0.65 0.02 260)" }}
                  labelFormatter={(value) => formatTimeOnly(value as number)}
                />
                <Area
                  type="monotone"
                  dataKey="logs"
                  stroke="oklch(0.65 0.2 250)"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorLogs)"
                  name="日志数量"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  )
}