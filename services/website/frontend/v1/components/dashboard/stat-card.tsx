"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import {
  FileText,
  AlertTriangle,
  Shield,
  Activity,
  Zap,
  Clock,
  TrendingUp,
  TrendingDown,
  Server,
  Database,
  Cpu,
  Network,
  Eye,
  Bug,
  Lock,
  Unlock,
  Users,
  Globe,
  Wifi,
  HardDrive,
} from "lucide-react"

const iconMap = {
  "file-text": FileText,
  "alert-triangle": AlertTriangle,
  shield: Shield,
  activity: Activity,
  zap: Zap,
  clock: Clock,
  "trending-up": TrendingUp,
  "trending-down": TrendingDown,
  server: Server,
  database: Database,
  cpu: Cpu,
  network: Network,
  eye: Eye,
  bug: Bug,
  lock: Lock,
  unlock: Unlock,
  users: Users,
  globe: Globe,
  wifi: Wifi,
  "hard-drive": HardDrive,
} as const

type IconName = keyof typeof iconMap

interface StatCardProps {
  title: string
  value: string | number
  change?: string
  changeType?: "positive" | "negative" | "neutral"
  iconName: IconName
  iconColor?: string
  description?: string
}

export function StatCard({
  title,
  value,
  change,
  changeType = "neutral",
  iconName,
  iconColor = "text-primary",
  description,
}: StatCardProps) {
  const Icon = iconMap[iconName]

  return (
    <Card className="relative overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <div className={cn("rounded-lg bg-muted p-2", iconColor)}>
          <Icon className="h-4 w-4" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {(change || description) && (
          <p className="mt-1 text-xs text-muted-foreground">
            {change && (
              <span
                className={cn(
                  "font-medium",
                  changeType === "positive" && "text-success",
                  changeType === "negative" && "text-destructive"
                )}
              >
                {change}
              </span>
            )}
            {change && description && " "}
            {description}
          </p>
        )}
      </CardContent>
      {/* Subtle gradient overlay */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent" />
    </Card>
  )
}
