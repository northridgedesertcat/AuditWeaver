"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  UserPlus,
  Ban,
  CheckCircle2,
  KeyRound,
  Trash2,
  ShieldCheck,
  Loader2,
  Users,
} from "lucide-react"
import { useAuth } from "@/lib/auth"
import {
  changeMyPassword,
  createAdmin,
  deleteAdmin,
  listAdmins,
  resetAdminPassword,
  setAdminActive,
  type AdminInfo,
} from "@/lib/api/auth"

interface Notice {
  type: "success" | "error"
  text: string
}

export default function AdminManagePage() {
  const { user, ready } = useAuth()
  const router = useRouter()

  const [admins, setAdmins] = useState<AdminInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState<Notice | null>(null)

  // 添加管理员表单
  const [createForm, setCreateForm] = useState({
    username: "",
    display_name: "",
    email: "",
    password: "",
    confirm: "",
  })
  const [creating, setCreating] = useState(false)

  // 行内重置密码
  const [resettingId, setResettingId] = useState<number | null>(null)
  const [resetPwd, setResetPwd] = useState({ pwd: "", confirm: "" })

  // 修改自己的密码
  const [myPwd, setMyPwd] = useState({ old: "", next: "", confirm: "" })
  const [savingMyPwd, setSavingMyPwd] = useState(false)

  const isRoot = !!user?.is_root_admin

  // 页面级守卫:非 Root 一律重定向首页(后端 IsRootAdmin 是最终防线)
  useEffect(() => {
    if (ready && !isRoot) router.replace("/")
  }, [ready, isRoot, router])

  const flash = useCallback((n: Notice) => {
    setNotice(n)
    const t = setTimeout(() => setNotice(null), 4000)
    return () => clearTimeout(t)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setAdmins(await listAdmins())
    } catch (e) {
      setNotice({ type: "error", text: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (ready && isRoot) load()
  }, [ready, isRoot, load])

  if (!ready || !isRoot) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        加载中...
      </div>
    )
  }

  async function handleCreate() {
    const f = createForm
    if (!f.username.trim()) return flash({ type: "error", text: "请填写用户名" })
    if (f.password !== f.confirm) return flash({ type: "error", text: "两次输入的密码不一致" })
    if (f.password.length < 8) return flash({ type: "error", text: "密码至少 8 位" })
    setCreating(true)
    try {
      await createAdmin({
        username: f.username.trim(),
        password: f.password,
        display_name: f.display_name.trim(),
        email: f.email.trim(),
      })
      setCreateForm({ username: "", display_name: "", email: "", password: "", confirm: "" })
      flash({ type: "success", text: `管理员 ${f.username} 创建成功` })
      await load()
    } catch (e) {
      flash({ type: "error", text: (e as Error).message })
    } finally {
      setCreating(false)
    }
  }

  async function toggleActive(a: AdminInfo) {
    try {
      await setAdminActive(a.id, !a.is_active)
      flash({
        type: "success",
        text: a.is_active ? `已禁用 ${a.username}` : `已启用 ${a.username}`,
      })
      await load()
    } catch (e) {
      flash({ type: "error", text: (e as Error).message })
    }
  }

  async function handleReset(id: number) {
    if (resetPwd.pwd !== resetPwd.confirm)
      return flash({ type: "error", text: "两次输入的密码不一致" })
    if (resetPwd.pwd.length < 8)
      return flash({ type: "error", text: "密码至少 8 位" })
    try {
      await resetAdminPassword(id, resetPwd.pwd)
      flash({ type: "success", text: "密码已重置,该用户需用新密码重新登录" })
      setResettingId(null)
      setResetPwd({ pwd: "", confirm: "" })
    } catch (e) {
      flash({ type: "error", text: (e as Error).message })
    }
  }

  async function handleDelete(a: AdminInfo) {
    if (!window.confirm(`确认删除管理员 ${a.username}?删除后不可恢复(建议优先使用禁用)。`)) return
    try {
      await deleteAdmin(a.id)
      flash({ type: "success", text: `已删除 ${a.username}` })
      await load()
    } catch (e) {
      flash({ type: "error", text: (e as Error).message })
    }
  }

  async function handleChangeMyPassword() {
    if (!myPwd.old) return flash({ type: "error", text: "请输入原密码" })
    if (myPwd.next !== myPwd.confirm)
      return flash({ type: "error", text: "两次输入的新密码不一致" })
    setSavingMyPwd(true)
    try {
      await changeMyPassword(myPwd.old, myPwd.next)
      setMyPwd({ old: "", next: "", confirm: "" })
      flash({ type: "success", text: "密码修改成功,请重新登录" })
    } catch (e) {
      flash({ type: "error", text: (e as Error).message })
    } finally {
      setSavingMyPwd(false)
    }
  }

  return (
    <DashboardLayout title="用户管理" subtitle="仅 Root Admin 可访问:创建、禁用、重置普通管理员">
      <div className="mx-auto max-w-5xl space-y-6">
        {notice && (
          <div
            className={
              notice.type === "success"
                ? "rounded-md border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-600 dark:text-green-400"
                : "rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive"
            }
          >
            {notice.text}
          </div>
        )}

        {/* 添加管理员 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <UserPlus className="h-4 w-4" />
              添加管理员
            </CardTitle>
            <CardDescription>
              新建的账号为普通管理员(Admin),可使用全部业务功能但不能管理用户
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="new-username">用户名 *</Label>
                <Input
                  id="new-username"
                  value={createForm.username}
                  onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
                  placeholder="登录用户名"
                  autoComplete="off"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-display">显示名称</Label>
                <Input
                  id="new-display"
                  value={createForm.display_name}
                  onChange={(e) => setCreateForm({ ...createForm, display_name: e.target.value })}
                  placeholder="如:张三"
                  autoComplete="off"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-email">邮箱</Label>
                <Input
                  id="new-email"
                  type="email"
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  placeholder="可选"
                  autoComplete="off"
                />
              </div>
              <div />
              <div className="space-y-2">
                <Label htmlFor="new-password">初始密码 *</Label>
                <Input
                  id="new-password"
                  type="password"
                  value={createForm.password}
                  onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                  placeholder="至少 8 位,需含一定复杂度"
                  autoComplete="new-password"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-confirm">确认密码 *</Label>
                <Input
                  id="new-confirm"
                  type="password"
                  value={createForm.confirm}
                  onChange={(e) => setCreateForm({ ...createForm, confirm: e.target.value })}
                  autoComplete="new-password"
                />
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <Button onClick={handleCreate} disabled={creating}>
                {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                创建管理员
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* 管理员列表(Root 不会出现:后端查询层已过滤 role=admin) */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4" />
              管理员列表
            </CardTitle>
            <CardDescription>禁用后该用户的登录态立即失效;重置密码会强制其重新登录</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-10 text-muted-foreground">
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                加载中...
              </div>
            ) : admins.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">暂无普通管理员</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>用户名</TableHead>
                    <TableHead>显示名称</TableHead>
                    <TableHead>邮箱</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {admins.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell className="font-medium">{a.username}</TableCell>
                      <TableCell>{a.display_name || "—"}</TableCell>
                      <TableCell className="text-muted-foreground">{a.email || "—"}</TableCell>
                      <TableCell>
                        {a.is_active ? (
                          <Badge className="bg-green-500/15 text-green-600 hover:bg-green-500/15 dark:text-green-400">
                            <CheckCircle2 className="mr-1 h-3 w-3" />
                            启用
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="bg-muted text-muted-foreground">
                            <Ban className="mr-1 h-3 w-3" />
                            已禁用
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setResettingId(resettingId === a.id ? null : a.id)
                              setResetPwd({ pwd: "", confirm: "" })
                            }}
                          >
                            <KeyRound className="mr-1 h-3.5 w-3.5" />
                            重置密码
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => toggleActive(a)}
                          >
                            {a.is_active ? (
                              <>
                                <Ban className="mr-1 h-3.5 w-3.5" />
                                禁用
                              </>
                            ) : (
                              <>
                                <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                                启用
                              </>
                            )}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => handleDelete(a)}
                          >
                            <Trash2 className="mr-1 h-3.5 w-3.5" />
                            删除
                          </Button>
                        </div>
                        {resettingId === a.id && (
                          <div className="mt-3 flex items-end justify-end gap-2 rounded-md border border-border bg-muted/30 p-3">
                            <div className="space-y-1">
                              <Label htmlFor={`reset-pwd-${a.id}`} className="text-xs">
                                为 {a.username} 设置新密码
                              </Label>
                              <Input
                                id={`reset-pwd-${a.id}`}
                                type="password"
                                className="h-8 w-52"
                                placeholder="新密码(至少 8 位)"
                                value={resetPwd.pwd}
                                onChange={(e) => setResetPwd({ ...resetPwd, pwd: e.target.value })}
                                autoComplete="new-password"
                              />
                            </div>
                            <Input
                              type="password"
                              className="h-8 w-40"
                              placeholder="确认新密码"
                              value={resetPwd.confirm}
                              onChange={(e) => setResetPwd({ ...resetPwd, confirm: e.target.value })}
                              autoComplete="new-password"
                            />
                            <Button size="sm" onClick={() => handleReset(a.id)}>
                              确认重置
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setResettingId(null)}
                            >
                              取消
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* 修改自己的密码 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-4 w-4" />
              修改我的密码
            </CardTitle>
            <CardDescription>
              当前登录:{user.username}(Root Admin)。修改成功后所有登录态失效,需用新密码重新登录
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="my-old">原密码</Label>
                <Input
                  id="my-old"
                  type="password"
                  value={myPwd.old}
                  onChange={(e) => setMyPwd({ ...myPwd, old: e.target.value })}
                  autoComplete="current-password"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="my-new">新密码</Label>
                <Input
                  id="my-new"
                  type="password"
                  value={myPwd.next}
                  onChange={(e) => setMyPwd({ ...myPwd, next: e.target.value })}
                  autoComplete="new-password"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="my-confirm">确认新密码</Label>
                <Input
                  id="my-confirm"
                  type="password"
                  value={myPwd.confirm}
                  onChange={(e) => setMyPwd({ ...myPwd, confirm: e.target.value })}
                  autoComplete="new-password"
                />
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <Button onClick={handleChangeMyPassword} disabled={savingMyPwd}>
                {savingMyPwd && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                修改密码
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
