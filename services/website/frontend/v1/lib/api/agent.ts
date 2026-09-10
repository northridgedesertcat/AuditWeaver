// Agent Service 前端封装:统一走 Django(相对路径,由 next.config rewrites 代理),固定 agent_type。
// 一版 agent_type 写死 analysis_explorer;新增 agent 时仅需改此处常量或由调用方传入。

import { apiFetch } from './client'

export type AgentEventType =
  | "token"
  | "tool_call"
  | "tool_result"
  | "done"
  | "error"

export interface AgentEvent {
  type: AgentEventType
  content?: string
  tool?: string
  args?: Record<string, unknown>
  summary?: string
}

export interface StreamAgentChatOptions {
  onToken?: (text: string) => void
  onToolCall?: (tool: string, args: Record<string, unknown>) => void
  onToolResult?: (tool: string, summary: string) => void
  onDone?: () => void
  onError?: (message: string) => void
  signal?: AbortSignal
}

export const DEFAULT_AGENT_TYPE = "analysis_explorer"

function dispatch(evt: AgentEvent, opts: StreamAgentChatOptions) {
  switch (evt.type) {
    case "token":
      if (evt.content) opts.onToken?.(evt.content)
      break
    case "tool_call":
      opts.onToolCall?.(evt.tool || "", evt.args || {})
      break
    case "tool_result":
      opts.onToolResult?.(evt.tool || "", evt.summary || "")
      break
    case "error":
      opts.onError?.(evt.content || "unknown error")
      break
    case "done":
      opts.onDone?.()
      break
  }
}

function parseEventPayload(block: string, opts: StreamAgentChatOptions) {
  const dataLine = block
    .split("\n")
    .find((l) => l.startsWith("data:"))
  if (!dataLine) return
  const payload = dataLine.slice(5).trim()
  if (!payload) return
  try {
    dispatch(JSON.parse(payload), opts)
  } catch {
    // 忽略非 JSON 数据行
  }
}

/** 流式对话:逐 token / 工具事件回调。 */
export async function streamAgentChat(
  message: string,
  threadId: string | null,
  agentType: string = DEFAULT_AGENT_TYPE,
  opts: StreamAgentChatOptions = {},
): Promise<void> {
  // 走 apiFetch:自动带 Bearer token;401 时自动 refresh 并重试一次。
  // SSE 同样适用——apiFetch 返回的是最终 Response,拿到后再开始读流。
  // 若 refresh 也失败,apiFetch 会清空 token 并跳转登录页。
  const resp = await apiFetch(`/agent/${agentType}/chat`, {
    method: "POST",
    headers: { Accept: "text/event-stream" },
    body: JSON.stringify({ message, thread_id: threadId, history: [] }),
    signal: opts.signal,
  })

  if (!resp.ok || !resp.body) {
    throw new Error(`agent chat failed: ${resp.status}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder("utf-8")
  let buffer = ""

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let sep: number
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      parseEventPayload(block, opts)
    }
  }

  // flush 残余
  if (buffer.trim()) {
    parseEventPayload(buffer, opts)
  }
}

/** 非流式对话:一次拿完整答案 + 工具调用清单。 */
export async function chatSync(
  message: string,
  threadId: string | null,
  agentType: string = DEFAULT_AGENT_TYPE,
): Promise<{
  answer: string
  toolCalls: { tool: string; args: Record<string, unknown>; summary: string }[]
  threadId: string | null
}> {
  const resp = await apiFetch(`/agent/${agentType}/chat/sync`, {
    method: "POST",
    body: JSON.stringify({ message, thread_id: threadId, history: [] }),
  })
  if (!resp.ok) throw new Error(`agent sync failed: ${resp.status}`)
  const data = await resp.json()
  return {
    answer: data.answer || "",
    toolCalls: data.tool_calls || [],
    threadId: data.thread_id ?? threadId,
  }
}
