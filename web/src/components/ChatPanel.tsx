import { useEffect, useRef } from "react";

import { AGENT_LABELS } from "../lib/agentMeta";
import type { AgentStatus, StreamLogEntry } from "../types";
import { StatusSteps } from "./StatusSteps";


const metadataLabels: Record<string, string> = {
  intent: "意图",
  intent_reason: "意图依据",
  company: "公司",
  role: "岗位",
  team_hint: "团队提示",
  domain_hint: "业务域",
  used_tools: "检索工具",
  search_queries: "检索词",
  evidence_count: "证据条数",
  source_urls: "证据链接",
  company_specific_source_count: "公司特异证据",
  generic_source_count: "泛化证据",
  context_quality_score: "证据质量分",
  business_domain_hints: "业务线索",
  search_failures: "检索失败",
  company_signals: "公司信号",
  role_signals: "岗位信号",
  company_specific_requirements: "公司特异要求",
  common_requirements: "通用要求",
  coverage_gaps: "证据缺口",
  core_evaluation_points: "核心考点",
  technical_stack_requirements: "技术栈",
  salary_signals: "薪资线索",
  interview_expectations: "面试官期待",
  candidate_risks: "风险点",
  interviewer_questions: "高压追问",
  prep_strategy: "准备动作",
  interview_angle: "面试官视角",
  evidence_gap_summary: "缺口总结",
  action_plan_source_coverage: "行动项证据覆盖",
  action_plan_items_count: "行动项数量",
  fallback_query: "Query 回退",
  fallback_insight: "Insight 回退",
  fallback_report: "Report 回退",
  issues: "审查问题",
  quality_score: "质量评分",
  retry_target: "回退目标",
};


function flattenMetadata(metadata: Record<string, unknown> | null | undefined): string[] {
  if (!metadata) {
    return [];
  }

  return Object.entries(metadata)
    .flatMap(([key, value]) => {
      const label = metadataLabels[key] ?? key;
      if (Array.isArray(value)) {
        return value.slice(0, 3).map((item) => `${label}: ${String(item)}`);
      }
      if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
        return [`${label}: ${String(value)}`];
      }
      return [];
    })
    .slice(0, 8);
}


export function ChatPanel({
  logs,
  agentStatuses,
  isLoading,
  maxRetries,
}: {
  logs: StreamLogEntry[];
  agentStatuses: AgentStatus[];
  isLoading: boolean;
  maxRetries: number;
}) {
  const logEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const doneCount = agentStatuses.filter((item) => item.status === "done").length;
  const runningAgent = agentStatuses.find((item) => item.status === "running");

  return (
    <div className="flex h-full flex-col gap-5 overflow-hidden">
      <section className="glass-panel shrink-0 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-500">
              Live Orchestration
            </p>
            <h2 className="mt-2 text-lg font-semibold text-slate-950">Agent 执行状态流</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              IntentRouter 先分流，Search 再按 intent 并发写入真实证据，Report 以 token 级方式流式成稿，
              Review 决定是否打回重写，最多允许 {maxRetries} 次重试。
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 text-right">
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Progress</div>
            <div className="mt-1 text-2xl font-semibold text-slate-950">
              {doneCount}/{agentStatuses.length}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {runningAgent ? `当前执行：${AGENT_LABELS[runningAgent.agent]}` : "等待新任务"}
            </div>
          </div>
        </div>

        <div className="mt-5">
          <StatusSteps statuses={agentStatuses} maxRetries={maxRetries} />
        </div>
      </section>

      <section className="glass-panel min-h-0 flex-1 overflow-hidden p-5">
        <div className="flex items-center justify-between gap-4 border-b border-slate-200 pb-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-500">
              Execution Trace
            </p>
            <h3 className="mt-2 text-lg font-semibold text-slate-950">交互与日志</h3>
          </div>
          {isLoading && (
            <div className="flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-900">
              <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
              正在流式生成
            </div>
          )}
        </div>

        <div className="mt-4 h-full overflow-y-auto pr-1">
          {logs.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-slate-300 bg-white/60 p-6 text-sm leading-7 text-slate-600">
              输入“公司 + 岗位 + 目标”后，左侧会实时显示 IntentRouter / Search / Query / Insight / Report /
              Review 的执行日志，右侧同步以打字机效果渲染 Markdown 报告。
            </div>
          ) : (
            <div className="space-y-3">
              {logs.map((log) => {
                const metadataLines = flattenMetadata(log.metadata);
                const isUser = log.kind === "user";
                const isError = log.kind === "error";
                const isWarning =
                  log.content.includes("LLM 不可用") ||
                  log.content.includes("熔断") ||
                  (log.agent === "ReviewAgent" &&
                    typeof log.metadata?.passed === "boolean" &&
                    log.metadata.passed === false);

                return (
                  <article
                    key={log.id}
                    className={`rounded-3xl border p-4 ${
                      isUser
                        ? "border-sky-200 bg-sky-50/90"
                        : isError
                        ? "border-rose-200 bg-rose-50/90"
                        : isWarning
                        ? "border-amber-200 bg-amber-50/90"
                        : "border-slate-200 bg-white/80"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                          {log.kind}
                        </p>
                        <h4 className="mt-1 text-sm font-semibold text-slate-950">{log.title}</h4>
                      </div>
                      <span className="text-xs text-slate-500">
                        {new Date(log.timestamp).toLocaleTimeString("zh-CN", {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        })}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-700">{log.content}</p>
                    {metadataLines.length > 0 && (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {metadataLines.map((line) => (
                          <span
                            key={`${log.id}-${line}`}
                            className="rounded-full border border-slate-200 bg-stone-50 px-3 py-1 text-xs text-slate-700"
                          >
                            {line}
                          </span>
                        ))}
                      </div>
                    )}
                  </article>
                );
              })}
              <div ref={logEndRef} />
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
