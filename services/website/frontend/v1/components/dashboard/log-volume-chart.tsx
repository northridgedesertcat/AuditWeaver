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

interface TrendData {
  time: string
  logs: number
}

const defaultData = [
  { time: "00:00", logs: 0 },
  { time: "02:00", logs: 0 },
  { time: "04:00", logs: 0 },
  { time: "06:00", logs: 0 },
  { time: "08:00", logs: 0 },
  { time: "10:00", logs: 0 },
  { time: "12:00", logs: 0 },
  { time: "14:00", logs: 0 },
  { time: "16:00", logs: 0 },
  { time: "18:00", logs: 0 },
  { time: "20:00", logs: 0 },
  { time: "22:00", logs: 0 },
]

function generateTimeLabels(): string[] {
  const labels: string[] = []
  const now = new Date()
  for (let i = 23; i >= 0; i--) {
    const hourAgo = new Date(now.getTime() - i * 60 * 60 * 1000)
    const hours = hourAgo.getHours().toString().padStart(2, '0')
    const minutes = hourAgo.getMinutes().toString().padStart(2, '0')
    labels.push(`${hours}:${minutes}`)
  }
  return labels
}

export function LogVolumeChart() {
  const [data, setData] = useState<TrendData[]>(defaultData)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchTrend = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/v1/logs/trend/")
        const result = await response.json()
        
        if (result.data && result.data.length > 0) {
          const timeLabels = generateTimeLabels()
          const mappedData: TrendData[] = result.data.map((item: TrendData, index: number) => ({
            time: timeLabels[index] || item.time,
            logs: item.logs
          }))
          setData(mappedData)
        } else {
          const timeLabels = generateTimeLabels()
          setData(timeLabels.map(time => ({ time, logs: 0 })))
        }
      } catch (error) {
        console.error("Failed to fetch log trend:", error)
        const timeLabels = generateTimeLabels()
        setData(timeLabels.map(time => ({ time, logs: 0 })))
      } finally {
        setLoading(false)
      }
    }

    fetchTrend()
    const interval = setInterval(fetchTrend, 30000)

    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const interval = setInterval(() => {
      const timeLabels = generateTimeLabels()
      setData(prevData => prevData.map((item, index) => ({
        ...item,
        time: timeLabels[index] || item.time
      })))
    }, 60000)

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
