import clsx from "clsx";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import dayjs from "dayjs";
import type { ChatMessage as ChatMessageType } from "../types";

const agentConfig: Record<string, { color: string; icon: string; name: string }> = {
  QueryAgent: {
    color: "from-blue-500 to-cyan-500",
    icon: "🔍",
    name: "岗位与公司扫描",
  },
  InsightAgent: {
    color: "from-purple-500 to-pink-500",
    icon: "🧭",
    name: "候选人洞察",
  },
  ReportAgent: {
    color: "from-green-500 to-emerald-500",
    icon: "📝",
    name: "求职报告生成",
  },
  System: {
    color: "from-slate-500 to-slate-600",
    icon: "⚙️",
    name: "系统",
  },
  User: {
    color: "from-indigo-500 to-blue-500",
    icon: "👤",
    name: "候选人",
  },
};

interface Props {
  message: ChatMessageType;
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";
  const agent = message.agent ?? "System";
  const config = agentConfig[agent] ?? agentConfig.System;
  const timestamp = dayjs(message.timestamp).format("HH:mm:ss");

  return (
    <div className={clsx("flex gap-4", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div
        className={clsx(
          "w-10 h-10 rounded-xl flex items-center justify-center text-white text-lg flex-shrink-0 shadow-lg",
          `bg-gradient-to-br ${config.color}`
        )}
      >
        {config.icon}
      </div>

      {/* Message Content */}
      <div className={clsx("flex-1 flex flex-col gap-2", isUser && "items-end")}>
        {/* Header */}
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-900">{config.name}</span>
          <span className="text-xs text-slate-500">{timestamp}</span>
          {message.pending && (
            <span className="text-xs text-blue-500 font-medium">生成中...</span>
          )}
        </div>

        {/* Message Bubble */}
        <div
          className={clsx(
            "rounded-2xl px-5 py-4 text-sm leading-relaxed shadow-sm max-w-3xl",
            isUser
              ? "bg-gradient-to-br from-blue-500 to-indigo-600 text-white"
              : "bg-white border border-slate-200 text-slate-900"
          )}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "");
                const isInline = !match;
                return isInline ? (
                  <code
                    className={clsx(
                      "rounded px-1.5 py-0.5 text-xs font-mono",
                      isUser
                        ? "bg-white/20 text-white"
                        : "bg-slate-100 text-slate-800"
                    )}
                    {...props}
                  >
                    {children}
                  </code>
                ) : (
                  <code
                    className={clsx(
                      "block rounded-lg p-3 text-xs font-mono overflow-x-auto",
                      isUser ? "bg-white/10 text-white" : "bg-slate-900 text-slate-100"
                    )}
                    {...props}
                  >
                    {children}
                  </code>
                );
              },
              a({ children, ...props }) {
                return (
                  <a
                    className={clsx(
                      "underline font-medium",
                      isUser ? "text-white/90" : "text-blue-600 hover:text-blue-700"
                    )}
                    target="_blank"
                    rel="noreferrer"
                    {...props}
                  >
                    {children}
                  </a>
                );
              },
              h1: ({ children }) => (
                <h1 className={clsx("text-xl font-bold mt-4 mb-2", isUser ? "text-white" : "text-slate-900")}>
                  {children}
                </h1>
              ),
              h2: ({ children }) => (
                <h2 className={clsx("text-lg font-bold mt-3 mb-2", isUser ? "text-white" : "text-slate-900")}>
                  {children}
                </h2>
              ),
              h3: ({ children }) => (
                <h3 className={clsx("text-base font-semibold mt-2 mb-1", isUser ? "text-white" : "text-slate-900")}>
                  {children}
                </h3>
              ),
              ul: ({ children }) => (
                <ul className={clsx("list-disc list-inside space-y-1 my-2", isUser ? "text-white/90" : "text-slate-700")}>
                  {children}
                </ul>
              ),
              ol: ({ children }) => (
                <ol className={clsx("list-decimal list-inside space-y-1 my-2", isUser ? "text-white/90" : "text-slate-700")}>
                  {children}
                </ol>
              ),
              p: ({ children }) => (
                <p className={clsx("my-2", isUser ? "text-white/90" : "text-slate-700")}>
                  {children}
                </p>
              ),
              blockquote: ({ children }) => (
                <blockquote
                  className={clsx(
                    "border-l-4 pl-4 my-2 italic",
                    isUser ? "border-white/30 text-white/80" : "border-slate-300 text-slate-600"
                  )}
                >
                  {children}
                </blockquote>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
