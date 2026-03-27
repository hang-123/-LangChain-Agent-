import type { ChatMessage } from "../types";
import { AGENT_LABELS } from "../lib/agentMeta";

interface Props {
  messages: ChatMessage[];
}

function normalizeMetadata(metadata: Record<string, unknown> | null | undefined) {
  if (!metadata) return [];
  const labelMap: Record<string, string> = {
    company: "公司",
    role: "岗位",
    candidate_goal: "目标",
    focus_points: "关注重点",
    likely_questions: "高频追问",
    prep_actions: "准备动作",
    candidate_risks: "风险点",
    prep_strategy: "准备策略",
    project_angles: "项目表达",
    interviewer_focus: "面试官关注点",
    generation_mode: "生成模式",
    detail_level: "输出等级",
  };

  return Object.entries(metadata)
    .filter(([key, value]) => key !== "llm_error" && value != null && (!Array.isArray(value) || value.length > 0))
    .map(([key, value]) => ({
      key,
      label: labelMap[key] ?? key,
      value,
    }));
}

export function AgentInsightsPanel({ messages }: Props) {
  const latestAgentMessages = ["QueryAgent", "InsightAgent", "ReportAgent"]
    .map((agent) => [...messages].reverse().find((message) => message.agent === agent && message.role === "agent"))
    .filter((message): message is ChatMessage => Boolean(message));

  if (latestAgentMessages.length === 0) {
    return (
      <div className="text-sm text-slate-500">
        运行一次任务后，这里会显示各个 Agent 的结构化中间结果和生成模式。
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {latestAgentMessages.map((message) => {
        const entries = normalizeMetadata(message.metadata);
        return (
          <div key={`${message.agent}-${message.timestamp}`} className="rounded-xl border border-slate-200 bg-white/80 p-3">
            <div className="mb-2 flex items-center justify-between">
              <div className="text-sm font-semibold text-slate-900">
                {AGENT_LABELS[message.agent ?? "System"] ?? message.agent}
              </div>
              {typeof message.metadata?.generation_mode === "string" && (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                  {String(message.metadata.generation_mode).toUpperCase()}
                </span>
              )}
            </div>
            {entries.length > 0 ? (
              <div className="space-y-2">
                {entries.map((entry) => (
                  <div key={entry.key}>
                    <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      {entry.label}
                    </div>
                    {Array.isArray(entry.value) ? (
                      <ul className="mt-1 space-y-1 text-xs text-slate-600">
                        {entry.value.map((item, idx) => (
                          <li key={`${entry.key}-${idx}`}>- {String(item)}</li>
                        ))}
                      </ul>
                    ) : (
                      <div className="mt-1 text-xs text-slate-600">{String(entry.value)}</div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500">当前节点没有额外结构化输出。</div>
            )}
            {typeof message.metadata?.llm_error === "string" && (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                已回退到本地模板模式：{String(message.metadata.llm_error)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
