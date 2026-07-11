"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Activity, Zap, Brain, Target } from "lucide-react"
import { cn } from "@/lib/utils"

const aiInsights = [
  {
    id: 1,
    type: "pattern",
    icon: Activity,
    title: "检测到新的攻击模式",
    description: "AI 发现来自东欧 IP 段的协同攻击行为，建议加强 WAF 规则",
    confidence: 94,
    time: "5 分钟前",
  },
  {
    id: 2,
    type: "anomaly",
    icon: Zap,
    title: "用户行为异常",
    description: "用户 admin_zhang 在非工作时间进行大量数据查询操作",
    confidence: 87,
    time: "12 分钟前",
  },
  {
    id: 3,
    type: "prediction",
    icon: Brain,
    title: "风险预测",
    description: "基于历史数据，预计未来 2 小时内可能出现 DDoS 攻击",
    confidence: 76,
    time: "25 分钟前",
  },
  {
    id: 4,
    type: "recommendation",
    icon: Target,
    title: "安全建议",
    description: "建议更新 SSL 证书，当前证书将在 15 天后过期",
    confidence: 100,
    time: "1 小时前",
  },
]

const typeConfig = {
  pattern: { label: "模式识别", color: "bg-primary/20 text-primary" },
  anomaly: { label: "异常检测", color: "bg-warning/20 text-warning" },
  prediction: { label: "风险预测", color: "bg-accent/20 text-accent" },
  recommendation: { label: "安全建议", color: "bg-success/20 text-success" },
}

export function AIInsights() {
  return (
    <Card className="col-span-2">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <Brain className="h-5 w-5 text-primary" />
          AI 智能洞察
        </CardTitle>
        <Badge variant="outline" className="text-xs">
          4 条新洞察
        </Badge>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-2">
          {aiInsights.map((insight) => {
            const config = typeConfig[insight.type as keyof typeof typeConfig]
            const Icon = insight.icon

            return (
              <div
                key={insight.id}
                className="flex gap-3 rounded-lg border border-border bg-card/50 p-4 transition-colors hover:bg-muted/30"
              >
                <div className="mt-0.5 rounded-lg bg-muted p-2">
                  <Icon className="h-4 w-4 text-primary" />
                </div>
                <div className="flex-1 space-y-1.5 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge className={cn("text-xs", config.color)}>
                      {config.label}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {insight.time}
                    </span>
                  </div>
                  <h4 className="text-sm font-medium">{insight.title}</h4>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {insight.description}
                  </p>
                  <div className="flex items-center gap-1 text-xs">
                    <span className="text-muted-foreground">置信度:</span>
                    <span className={cn(
                      "font-medium",
                      insight.confidence >= 90 ? "text-success" :
                      insight.confidence >= 75 ? "text-warning" : "text-muted-foreground"
                    )}>
                      {insight.confidence}%
                    </span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
