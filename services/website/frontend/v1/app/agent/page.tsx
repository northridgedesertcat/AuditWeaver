"use client"

import { useState, useRef, useEffect } from "react"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  Brain,
  Send,
  Sparkles,
  AlertTriangle,
  Shield,
  FileText,
  Search,
  Zap,
  Loader2,
  Copy,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  Lightbulb,
  Terminal,
  Database,
  Globe,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { formatRelative } from "@/lib/time"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: number
  isLoading?: boolean
  actions?: { label: string; action: string }[]
  data?: {
    type: "threat" | "logs" | "analysis" | "code"
    content: unknown
  }
}

const initialMessages: Message[] = [
  {
    id: "1",
    role: "assistant",
    content: "你好！我是 LogSentinel AI 安全助手。我可以帮助你分析日志、检测威胁、调查安全事件，或回答任何与安全运营相关的问题。你想了解什么？",
    timestamp: Date.now() - 60000,
    actions: [
      { label: "分析最近的威胁", action: "analyze_threats" },
      { label: "查看异常日志", action: "view_anomalies" },
      { label: "生成安全报告", action: "generate_report" },
    ],
  },
]

const suggestedQuestions = [
  {
    icon: AlertTriangle,
    text: "分析过去 24 小时内的高危告警",
  },
  {
    icon: Search,
    text: "搜索来自 IP 192.168.1.105 的所有日志",
  },
  {
    icon: Shield,
    text: "检查是否存在 SQL 注入攻击迹象",
  },
  {
    icon: FileText,
    text: "生成本周安全事件摘要报告",
  },
]

const quickActions = [
  { icon: AlertTriangle, label: "威胁分析", color: "text-destructive" },
  { icon: Search, label: "日志搜索", color: "text-primary" },
  { icon: Shield, label: "安全检查", color: "text-success" },
  { icon: Zap, label: "自动化", color: "text-warning" },
]

export default function AgentPage() {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: Date.now(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput("")
    setIsLoading(true)

    // Simulate AI response
    const loadingMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: "",
      timestamp: Date.now(),
      isLoading: true,
    }
    setMessages((prev) => [...prev, loadingMessage])

    // Simulate API delay
    await new Promise((resolve) => setTimeout(resolve, 1500))

    // Generate mock response based on input
    let responseContent = ""
    let responseData: Message["data"]
    let actions: Message["actions"]

    if (input.toLowerCase().includes("威胁") || input.toLowerCase().includes("告警")) {
      responseContent = `根据对过去 24 小时安全数据的分析，我发现了以下关键威胁：

**高危威胁 (3 件)**
1. **SQL 注入攻击** - 来源 IP: 185.234.12.45
   - 时间: 今天 14:32
   - 目标: /api/users/login
   - 状态: 已阻止

2. **暴力破解尝试** - 来源 IP: 10.0.0.45
   - 时间: 今天 12:15
   - 目标: SSH 服务
   - 尝试次数: 1,247 次

3. **可疑数据导出** - 用户: service_account_01
   - 时间: 今天 10:28
   - 数据量: 2.3GB (异常)
   - 状态: 需要调查

**建议措施：**
- 立即封禁 IP 185.234.12.45
- 检查 service_account_01 的权限配置
- 加强 SSH 服务的访问控制`
      responseData = { type: "threat", content: { count: 3, severity: "high" } }
      actions = [
        { label: "封禁可疑 IP", action: "block_ip" },
        { label: "查看详细日志", action: "view_logs" },
        { label: "创建事件工单", action: "create_incident" },
      ]
    } else if (input.toLowerCase().includes("日志") || input.toLowerCase().includes("搜索")) {
      responseContent = `已为你搜索相关日志记录。以下是最近的匹配结果：

\`\`\`
[2024-01-15 14:32:18] ERROR web-server-01 - Failed login attempt for user admin@example.com from IP 192.168.1.105
[2024-01-15 14:32:15] WARN api-gateway - Rate limit exceeded for API key: ak_live_xxx
[2024-01-15 14:32:12] INFO db-primary - Slow query detected: SELECT * FROM users WHERE... (2.3s)
[2024-01-15 14:32:10] ERROR payment-service - Payment processing failed: Card declined
[2024-01-15 14:32:08] INFO web-server-02 - GET /api/users/profile - 200 OK (45ms)
\`\`\`

共找到 **2,345** 条匹配日志。是否需要我进一步分析这些日志中的异常模式？`
      responseData = { type: "logs", content: { count: 2345 } }
      actions = [
        { label: "分析异常模式", action: "analyze_patterns" },
        { label: "导出日志", action: "export_logs" },
        { label: "设置告警规则", action: "create_alert" },
      ]
    } else if (input.toLowerCase().includes("报告") || input.toLowerCase().includes("摘要")) {
      responseContent = `# 本周安全事件摘要报告

**报告期间**: 2024-01-08 至 2024-01-15

## 总体概况
- 总日志量: 16.2M 条
- 安全事件: 47 起
- 威胁检测: 1,234 次
- 平均响应时间: 23 分钟

## 威胁分布
| 类型 | 数量 | 趋势 |
|------|------|------|
| 暴力破解 | 523 | ↑ 12% |
| SQL 注入 | 89 | ↓ 5% |
| XSS 攻击 | 156 | ↑ 8% |
| 数据泄露 | 12 | → 0% |

## 关键建议
1. 加强 Web 应用防火墙规则
2. 实施多因素认证
3. 更新 SSL 证书（15 天后过期）

需要我生成完整的 PDF 报告吗？`
      responseData = { type: "analysis", content: { period: "weekly" } }
      actions = [
        { label: "生成 PDF", action: "generate_pdf" },
        { label: "发送邮件", action: "send_email" },
        { label: "安排定期报告", action: "schedule_report" },
      ]
    } else {
      responseContent = `我理解你的问题。作为 AI 安全助手，我可以帮助你：

1. **威胁分析** - 分析潜在的安全威胁和攻击模式
2. **日志搜索** - 快速搜索和分析海量日志数据
3. **事件调查** - 协助安全事件的调查和响应
4. **报告生成** - 自动生成各类安全报告
5. **规则建议** - 提供安全策略和规则优化建议

请告诉我具体需要什么帮助？`
      actions = [
        { label: "分析最近威胁", action: "analyze_threats" },
        { label: "搜索日志", action: "search_logs" },
        { label: "查看安全状态", action: "security_status" },
      ]
    }

    setMessages((prev) =>
      prev.map((msg) =>
        msg.isLoading
          ? {
              ...msg,
              content: responseContent,
              isLoading: false,
              data: responseData,
              actions,
            }
          : msg
      )
    )
    setIsLoading(false)
  }

  const handleQuestionClick = (question: string) => {
    setInput(question)
  }

  const handleActionClick = (action: string) => {
    setInput(`执行操作: ${action}`)
  }

  return (
    <DashboardLayout
      title="AI 安全智能体"
      subtitle="智能对话式安全分析与运营助手"
    >
      <div className="grid gap-4 lg:grid-cols-4 h-[calc(100vh-12rem)]">
        {/* Sidebar */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              快捷操作
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              {quickActions.map((action) => {
                const Icon = action.icon
                return (
                  <Button
                    key={action.label}
                    variant="outline"
                    className="flex flex-col items-center gap-2 h-auto py-4"
                    onClick={() => handleActionClick(action.label)}
                  >
                    <Icon className={cn("h-5 w-5", action.color)} />
                    <span className="text-xs">{action.label}</span>
                  </Button>
                )
              })}
            </div>

            <div className="space-y-2">
              <p className="text-xs text-muted-foreground font-medium">推荐问题</p>
              {suggestedQuestions.map((question, index) => {
                const Icon = question.icon
                return (
                  <button
                    key={index}
                    className="flex items-start gap-2 w-full rounded-lg border border-border p-3 text-left text-sm transition-colors hover:bg-muted"
                    onClick={() => handleQuestionClick(question.text)}
                  >
                    <Icon className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
                    <span className="text-muted-foreground">{question.text}</span>
                  </button>
                )
              })}
            </div>

            <div className="pt-2 border-t border-border">
              <p className="text-xs text-muted-foreground mb-2">能力说明</p>
              <div className="space-y-2 text-xs text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Terminal className="h-3 w-3" />
                  <span>自然语言日志查询</span>
                </div>
                <div className="flex items-center gap-2">
                  <Database className="h-3 w-3" />
                  <span>跨数据源关联分析</span>
                </div>
                <div className="flex items-center gap-2">
                  <Globe className="h-3 w-3" />
                  <span>威胁情报整合</span>
                </div>
                <div className="flex items-center gap-2">
                  <Lightbulb className="h-3 w-3" />
                  <span>智能安全建议</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Chat Area */}
        <Card className="lg:col-span-3 flex flex-col">
          <CardHeader className="pb-3 border-b border-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center">
                  <Brain className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-base font-medium">LogSentinel AI</CardTitle>
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-success" />
                    在线 | 模型版本 v3.2
                  </p>
                </div>
              </div>
              <Button variant="ghost" size="sm">
                <RotateCcw className="mr-2 h-4 w-4" />
                新对话
              </Button>
            </div>
          </CardHeader>

          {/* Messages */}
          <ScrollArea className="flex-1 p-4" ref={scrollRef}>
            <div className="space-y-4 max-w-3xl mx-auto">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    "flex gap-3",
                    message.role === "user" && "flex-row-reverse"
                  )}
                >
                  <Avatar className="h-8 w-8 shrink-0">
                    <AvatarFallback
                      className={cn(
                        message.role === "assistant"
                          ? "bg-primary/20 text-primary"
                          : "bg-muted text-muted-foreground"
                      )}
                    >
                      {message.role === "assistant" ? (
                        <Brain className="h-4 w-4" />
                      ) : (
                        "我"
                      )}
                    </AvatarFallback>
                  </Avatar>
                  <div
                    className={cn(
                      "flex-1 space-y-2",
                      message.role === "user" && "flex flex-col items-end"
                    )}
                  >
                    <div
                      className={cn(
                        "rounded-lg px-4 py-3 max-w-[85%]",
                        message.role === "assistant"
                          ? "bg-muted"
                          : "bg-primary text-primary-foreground"
                      )}
                    >
                      {message.isLoading ? (
                        <div className="flex items-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          <span className="text-sm">正在分析...</span>
                        </div>
                      ) : (
                        <div className="text-sm whitespace-pre-wrap prose prose-sm dark:prose-invert max-w-none">
                          {message.content}
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    {message.actions && !message.isLoading && (
                      <div className="flex flex-wrap gap-2">
                        {message.actions.map((action) => (
                          <Button
                            key={action.action}
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => handleActionClick(action.label)}
                          >
                            {action.label}
                          </Button>
                        ))}
                      </div>
                    )}

                    {/* Message Actions */}
                    {message.role === "assistant" && !message.isLoading && (
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" className="h-7 w-7">
                          <Copy className="h-3 w-3" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7">
                          <ThumbsUp className="h-3 w-3" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7">
                          <ThumbsDown className="h-3 w-3" />
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>

          {/* Input */}
          <div className="border-t border-border p-4">
            <div className="max-w-3xl mx-auto">
              <div className="relative">
                <Textarea
                  placeholder="输入你的问题，例如：分析最近的威胁告警..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault()
                      handleSend()
                    }
                  }}
                  className="min-h-[80px] pr-12 resize-none"
                />
                <Button
                  size="icon"
                  className="absolute bottom-2 right-2"
                  onClick={handleSend}
                  disabled={!input.trim() || isLoading}
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <p className="mt-2 text-xs text-muted-foreground text-center">
                AI 助手可能会产生错误信息，请验证重要的安全决策
              </p>
            </div>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  )
}
