import { AGENT_DESCRIPTIONS, AGENT_LABELS } from "../lib/agentMeta";
import type { AgentStatus } from "../types";


const statusStyles: Record<AgentStatus["status"], string> = {
  idle: "border-stone-200 bg-white/70 text-slate-500",
  running: "border-amber-300 bg-amber-50 text-amber-900 shadow-[0_12px_32px_rgba(217,119,6,0.12)]",
  done: "border-emerald-300 bg-emerald-50 text-emerald-900",
  error: "border-rose-300 bg-rose-50 text-rose-900",
};


export function StatusSteps({
  statuses,
  maxRetries,
}: {
  statuses: AgentStatus[];
  maxRetries: number;
}) {
  return (
    <div className="grid gap-3">
      {statuses.map((item, index) => (
        <article
          key={item.agent}
          className={`rounded-2xl border px-4 py-4 transition-all ${statusStyles[item.status]}`}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500/80">
                Step {index + 1}
              </div>
              <h3 className="mt-1 text-sm font-semibold text-slate-900">{AGENT_LABELS[item.agent]}</h3>
              <p className="mt-1 text-xs leading-5 text-slate-600">{AGENT_DESCRIPTIONS[item.agent]}</p>
            </div>
            <div className="rounded-full border border-current/15 px-2.5 py-1 text-[11px] font-medium">
              {item.status === "idle" && "等待"}
              {item.status === "running" && "执行中"}
              {item.status === "done" && "完成"}
              {item.status === "error" && "异常"}
            </div>
          </div>
          <p className="mt-3 text-xs leading-5 text-slate-700">{item.detail}</p>
          {item.agent === "ReviewAgent" && (
            <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
              Retry Budget: {item.retryCount}/{maxRetries}
            </p>
          )}
        </article>
      ))}
    </div>
  );
}
