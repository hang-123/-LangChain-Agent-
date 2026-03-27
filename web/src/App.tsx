import type { FormEvent } from "react";
import { useState, useRef, useEffect } from "react";
import { useForumChat } from "./hooks/useForumChat";
import { ChatMessage } from "./components/ChatMessage";
import { AgentStatusPanel } from "./components/AgentStatusPanel";
import { AgentInsightsPanel } from "./components/AgentInsightsPanel";
import { ReportViewer } from "./components/ReportViewer";
import { SessionHistory } from "./components/SessionHistory";
import { AGENT_SHORT_DESCRIPTIONS } from "./lib/agentMeta";

type ViewMode = "chat" | "report";

const quickPrompts = [
  "帮我为字节跳动后端开发暑期实习生成一份求职研究报告，重点分析岗位要求、核心技术栈和面试准备方向。",
  "我准备投递小红书数据平台后端实习，请整理公司背景、岗位能力要求、常见面试题和一周准备建议。",
  "针对阿里云平台工程实习，帮我从岗位职责、业务背景、公开口碑和行动清单四个维度给出求职建议。",
];

export default function App() {
  const {
    messages,
    agentStatuses,
    isLoading,
    sendQuery,
    reset,
    templateId,
    setTemplateId,
    reportMarkdown,
    sessionId,
    error,
  } = useForumChat();
  const [queryDraft, setQueryDraft] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("chat");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!isLoading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isLoading]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!queryDraft.trim() || isLoading) return;
    const query = queryDraft.trim();
    setQueryDraft("");
    await sendQuery(query, true);
    setViewMode("chat");
  };

  const hasReport = !!reportMarkdown;
  const hasMessages = messages.length > 0;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.14),_transparent_30%),radial-gradient(circle_at_right,_rgba(16,185,129,0.12),_transparent_24%),linear-gradient(180deg,_#f8fafc_0%,_#eef6ff_48%,_#f8fafc_100%)] flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-slate-200/60 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                  <span className="text-white font-bold text-sm">BF</span>
                </div>
                <div>
                  <h1 className="text-lg font-bold bg-gradient-to-r from-sky-700 to-emerald-600 bg-clip-text text-transparent">
                    Career Research Copilot
                  </h1>
                  <p className="text-xs text-slate-500">多 Agent 求职研究助手</p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* View Mode Toggle */}
              {hasReport && (
                <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
                  <button
                    onClick={() => setViewMode("chat")}
                    className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                      viewMode === "chat"
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    对话
                  </button>
                  <button
                    onClick={() => setViewMode("report")}
                    className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                      viewMode === "report"
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    报告
                  </button>
                </div>
              )}

              {/* Template Selector */}
              <select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="executive">简洁输出</option>
                <option value="default">标准输出</option>
                <option value="analysis">详细输出</option>
              </select>

              {/* Sidebar Toggle */}
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
                title={sidebarOpen ? "隐藏侧边栏" : "显示侧边栏"}
              >
                <svg
                  className="w-5 h-5 text-slate-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                </svg>
              </button>

              {/* Reset Button */}
              {hasMessages && (
                <button
                  onClick={reset}
                  className="px-4 py-1.5 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  清空
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden max-w-7xl mx-auto w-full">
        {/* Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Input Area */}
          <div className="px-4 sm:px-6 lg:px-8 py-4 border-b border-slate-200/60 bg-white/50">
            <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
              <div className="flex items-end gap-3">
                <div className="flex-1 relative">
                  <input
                    ref={inputRef}
                    value={queryDraft}
                    onChange={(e) => setQueryDraft(e.target.value)}
                    placeholder="输入岗位、公司、面试目标或准备问题..."
                    disabled={isLoading}
                    className="w-full px-4 py-3 pr-12 text-base border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-slate-50 disabled:cursor-not-allowed transition-all"
                  />
                  {isLoading && (
                    <div className="absolute right-4 top-1/2 -translate-y-1/2">
                      <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                    </div>
                  )}
                </div>
                <button
                  type="submit"
                  disabled={!queryDraft.trim() || isLoading}
                  className="px-6 py-3 bg-gradient-to-r from-sky-600 to-emerald-600 text-white font-medium rounded-xl hover:from-sky-700 hover:to-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-sky-500/30 hover:shadow-xl hover:shadow-emerald-500/30"
                >
                  {isLoading ? "分析中..." : "开始生成"}
                </button>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {quickPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    disabled={isLoading}
                    onClick={() => setQueryDraft(prompt)}
                    className="rounded-full border border-sky-200 bg-white/80 px-3 py-1.5 text-xs text-slate-700 transition hover:border-sky-400 hover:text-sky-700 disabled:opacity-50"
                  >
                    {prompt.slice(0, 22)}...
                  </button>
                ))}
              </div>
              {error && (
                <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {error}
                </div>
              )}
            </form>
          </div>

          {/* Content Area */}
          <div className="flex-1 overflow-hidden">
            {viewMode === "chat" ? (
              <div className="h-full overflow-y-auto px-4 sm:px-6 lg:px-8 py-6">
                {!hasMessages ? (
                  <div className="max-w-3xl mx-auto mt-20 text-center">
                    <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                      <svg
                        className="w-10 h-10 text-white"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                        />
                      </svg>
                    </div>
                    <h2 className="text-2xl font-bold text-slate-900 mb-2">开始一次求职研究</h2>
                    <p className="text-slate-600 mb-8">
                      输入岗位、公司或面试目标，系统会协调多个 Agent 输出结构化求职研究报告
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl mx-auto">
                      {[
                        { icon: "🔍", title: "岗位与公司扫描", desc: AGENT_SHORT_DESCRIPTIONS.QueryAgent },
                        { icon: "🧭", title: "候选人洞察", desc: AGENT_SHORT_DESCRIPTIONS.InsightAgent },
                        { icon: "📝", title: "求职报告生成", desc: AGENT_SHORT_DESCRIPTIONS.ReportAgent },
                      ].map((item) => (
                        <div
                          key={item.title}
                          className="p-4 bg-white rounded-xl border border-slate-200 hover:border-blue-300 hover:shadow-md transition-all"
                        >
                          <div className="text-2xl mb-2">{item.icon}</div>
                          <div className="font-semibold text-slate-900 mb-1">{item.title}</div>
                          <div className="text-sm text-slate-600">{item.desc}</div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-8 rounded-2xl border border-slate-200 bg-white/70 p-5 text-left shadow-sm">
                      <div className="mb-3 text-sm font-semibold text-slate-900">这次演示会产出</div>
                      <div className="grid gap-3 text-sm text-slate-600 md:grid-cols-3">
                        <div>岗位关键信息提炼与公司背景概览</div>
                        <div>面试问题预测与回答准备建议</div>
                        <div>带会话记忆的行动清单与下一步规划</div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="max-w-4xl mx-auto space-y-6">
                    {messages.map((message) => (
                      <ChatMessage key={message.id} message={message} />
                    ))}
                    {isLoading && (
                      <div className="flex items-center gap-2 text-slate-500">
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }}></div>
                        <span className="ml-2">正在生成中...</span>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>
            ) : (
              <ReportViewer reportMarkdown={reportMarkdown} />
            )}
          </div>
        </main>

        {/* Sidebar */}
        {sidebarOpen && (
          <aside className="w-80 border-l border-slate-200/60 bg-white/50 flex flex-col">
            <div className="p-4 border-b border-slate-200/60">
              <h2 className="font-semibold text-slate-900 mb-2">Agent 执行状态</h2>
              <p className="mb-4 text-xs text-slate-500">SSE 实时驱动的顺序编排视图</p>
              <AgentStatusPanel statuses={agentStatuses} />
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <div className="space-y-6">
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-slate-900">Agent 中间结果</h3>
                  <AgentInsightsPanel messages={messages} />
                </div>
                <SessionHistory sessionId={sessionId} />
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
