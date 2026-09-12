"use client"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { cn } from "@/lib/utils"

/**
 * Markdown 渲染组件(GFM 完整支持)。
 *
 * 用于 Agent / Workflow 等 AI 文本输出的渲染,支持:
 * - 标题 / 粗体 / 斜体 / 删除线 / 行内代码
 * - 有序 / 无序列表、任务列表
 * - 表格、引用块、分隔线
 * - 代码块(带语言标识 + 深色背景)
 * - 链接(新标签页打开)
 *
 * 暗色主题适配:继承父容器文字色,代码块用深色背景。
 */
export function Markdown({
  content,
  className,
}: {
  content: string
  className?: string
}) {
  return (
    <div
      className={cn(
        "prose prose-sm dark:prose-invert max-w-none",
        // prose 默认 margin 较宽,在聊天气泡内收紧
        "prose-headings:mt-3 prose-headings:mb-2 prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-pre:my-2",
        "prose-code:before:content-none prose-code:after:content-none",
        className
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // 代码块:深色背景 + 横向滚动
          pre: ({ children, ...props }) => (
            <pre
              {...props}
              className="bg-muted/80 border border-border rounded-md p-3 overflow-x-auto text-xs"
            >
              {children}
            </pre>
          ),
          // 行内代码
          code: ({ className, children, ...props }) => {
            const isBlock = /language-/.test(className || "")
            return (
              <code
                {...props}
                className={
                  isBlock
                    ? "bg-transparent p-0 text-inherit"
                    : "bg-muted px-1.5 py-0.5 rounded text-[0.85em] font-mono"
                }
              >
                {children}
              </code>
            )
          },
          // 表格:边框 + 单元格内边距
          table: ({ children }) => (
            <div className="overflow-x-auto my-2">
              <table className="border-collapse border border-border text-sm">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-border px-3 py-1.5 bg-muted/60 text-left font-medium">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-border px-3 py-1.5">{children}</td>
          ),
          // 链接:新标签页打开 + 主题色
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline underline-offset-2 hover:opacity-80"
            >
              {children}
            </a>
          ),
          // 引用块:左侧竖线 + 浅色背景
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-primary/40 pl-3 py-1 my-2 text-muted-foreground italic">
              {children}
            </blockquote>
          ),
          // 任务列表复选框
          input: ({ type, checked }) => {
            if (type === "checkbox") {
              return (
                <input
                  type="checkbox"
                  checked={checked}
                  readOnly
                  className="mr-1.5 align-middle"
                />
              )
            }
            return <input type={type} checked={checked} readOnly />
          },
          // 分隔线
          hr: () => <hr className="my-3 border-border" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
