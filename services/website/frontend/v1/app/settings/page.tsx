"use client"

import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Settings,
  User,
  Bell,
  Shield,
  Database,
  Key,
  Mail,
  Globe,
  Palette,
  Clock,
  Save,
} from "lucide-react"

export default function SettingsPage() {
  return (
    <DashboardLayout
      title="系统设置"
      subtitle="平台配置与偏好设置"
    >
      <Tabs defaultValue="general" className="space-y-4">
        <TabsList className="flex-wrap h-auto gap-2">
          <TabsTrigger value="general">
            <Settings className="mr-2 h-4 w-4" />
            常规设置
          </TabsTrigger>
          <TabsTrigger value="notifications">
            <Bell className="mr-2 h-4 w-4" />
            通知设置
          </TabsTrigger>
          <TabsTrigger value="security">
            <Shield className="mr-2 h-4 w-4" />
            安全设置
          </TabsTrigger>
          <TabsTrigger value="integrations">
            <Database className="mr-2 h-4 w-4" />
            集成配置
          </TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">基本信息</CardTitle>
              <CardDescription>管理平台的基本配置信息</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="org-name">组织名称</Label>
                  <Input id="org-name" defaultValue="示例企业" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="admin-email">管理员邮箱</Label>
                  <Input id="admin-email" type="email" defaultValue="admin@example.com" />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="timezone">时区设置</Label>
                <Select defaultValue="asia-shanghai">
                  <SelectTrigger>
                    <SelectValue placeholder="选择时区" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="asia-shanghai">亚洲/上海 (UTC+8)</SelectItem>
                    <SelectItem value="asia-tokyo">亚洲/东京 (UTC+9)</SelectItem>
                    <SelectItem value="america-newyork">美洲/纽约 (UTC-5)</SelectItem>
                    <SelectItem value="europe-london">欧洲/伦敦 (UTC+0)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="language">界面语言</Label>
                <Select defaultValue="zh-CN">
                  <SelectTrigger>
                    <SelectValue placeholder="选择语言" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="zh-CN">简体中文</SelectItem>
                    <SelectItem value="en-US">English</SelectItem>
                    <SelectItem value="ja-JP">日本語</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">显示设置</CardTitle>
              <CardDescription>自定义界面显示偏好</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>深色模式</Label>
                  <p className="text-sm text-muted-foreground">启用深色主题</p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>紧凑模式</Label>
                  <p className="text-sm text-muted-foreground">减少界面元素间距</p>
                </div>
                <Switch />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>显示实时数据</Label>
                  <p className="text-sm text-muted-foreground">自动刷新仪表板数据</p>
                </div>
                <Switch defaultChecked />
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button>
              <Save className="mr-2 h-4 w-4" />
              保存更改
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="notifications" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">通知偏好</CardTitle>
              <CardDescription>配置告警和通知方式</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>邮件通知</Label>
                  <p className="text-sm text-muted-foreground">接收重要告警邮件</p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>浏览器通知</Label>
                  <p className="text-sm text-muted-foreground">启用桌面推送通知</p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>短信通知</Label>
                  <p className="text-sm text-muted-foreground">严重告警时发送短信</p>
                </div>
                <Switch />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Webhook 通知</Label>
                  <p className="text-sm text-muted-foreground">发送到自定义 Webhook</p>
                </div>
                <Switch />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">通知级别</CardTitle>
              <CardDescription>选择接收通知的告警级别</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>严重告警</Label>
                  <p className="text-sm text-muted-foreground">需要立即处理的安全事件</p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>高危告警</Label>
                  <p className="text-sm text-muted-foreground">重要的安全威胁</p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>中危告警</Label>
                  <p className="text-sm text-muted-foreground">需要关注的安全问题</p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>低危告警</Label>
                  <p className="text-sm text-muted-foreground">一般性安全提示</p>
                </div>
                <Switch />
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button>
              <Save className="mr-2 h-4 w-4" />
              保存更改
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="security" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">访问控制</CardTitle>
              <CardDescription>管理账户安全设置</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>双因素认证</Label>
                  <p className="text-sm text-muted-foreground">启用 2FA 增强安全性</p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>会话超时</Label>
                  <p className="text-sm text-muted-foreground">自动登出空闲会话</p>
                </div>
                <Select defaultValue="30">
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="15">15 分钟</SelectItem>
                    <SelectItem value="30">30 分钟</SelectItem>
                    <SelectItem value="60">1 小时</SelectItem>
                    <SelectItem value="never">从不</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>IP 白名单</Label>
                  <p className="text-sm text-muted-foreground">限制允许访问的 IP 地址</p>
                </div>
                <Switch />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">API 密钥</CardTitle>
              <CardDescription>管理 API 访问密钥</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <Input
                    value="sk_live_****************************"
                    readOnly
                    className="font-mono"
                  />
                </div>
                <Button variant="outline">
                  <Key className="mr-2 h-4 w-4" />
                  重新生成
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                API 密钥用于程序化访问平台功能，请妥善保管
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">审计日志</CardTitle>
              <CardDescription>配置审计日志设置</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>记录用户操作</Label>
                  <p className="text-sm text-muted-foreground">记录所有用户操作行为</p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>日志保留期限</Label>
                  <p className="text-sm text-muted-foreground">审计日志保存时间</p>
                </div>
                <Select defaultValue="90">
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="30">30 天</SelectItem>
                    <SelectItem value="90">90 天</SelectItem>
                    <SelectItem value="180">180 天</SelectItem>
                    <SelectItem value="365">1 年</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button>
              <Save className="mr-2 h-4 w-4" />
              保存更改
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="integrations" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">SIEM 集成</CardTitle>
              <CardDescription>配置与外部 SIEM 系统的集成</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Splunk</Label>
                  <div className="flex items-center gap-2">
                    <Input placeholder="https://splunk.example.com:8088" />
                    <Switch />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Elasticsearch</Label>
                  <div className="flex items-center gap-2">
                    <Input placeholder="https://elastic.example.com:9200" />
                    <Switch />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">通知集成</CardTitle>
              <CardDescription>配置外部通知渠道</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Slack Webhook</Label>
                  <Input placeholder="https://hooks.slack.com/services/..." />
                </div>
                <div className="space-y-2">
                  <Label>钉钉 Webhook</Label>
                  <Input placeholder="https://oapi.dingtalk.com/robot/send?..." />
                </div>
                <div className="space-y-2">
                  <Label>企业微信 Webhook</Label>
                  <Input placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?..." />
                </div>
                <div className="space-y-2">
                  <Label>PagerDuty</Label>
                  <Input placeholder="Integration Key" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">威胁情报集成</CardTitle>
              <CardDescription>配置威胁情报数据源</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>VirusTotal API Key</Label>
                  <Input type="password" placeholder="API Key" />
                </div>
                <div className="space-y-2">
                  <Label>AbuseIPDB API Key</Label>
                  <Input type="password" placeholder="API Key" />
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button>
              <Save className="mr-2 h-4 w-4" />
              保存更改
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </DashboardLayout>
  )
}
