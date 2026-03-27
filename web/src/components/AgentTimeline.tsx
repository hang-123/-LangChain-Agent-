import clsx from "clsx";
import type { AgentStatus } from "../types";

interface Props {
  statuses: AgentStatus[];
}

export function AgentTimeline({ statuses }: Props) {
  return (
    <ol className="space-y-3 text-sm">
      {statuses.map((status) => (
        <li key={status.agent} className="flex items-start gap-3">
          <span
            className={clsx(
              "w-3 h-3 rounded-full mt-1",
              status.status === "done" && "bg-accent shadow-lg shadow-emerald-500/40",
              status.status === "running" && "bg-yellow-400 animate-pulse",
              status.status === "idle" && "bg-slate-600"
            )}
          ></span>
          <div>
            <p className="font-semibold text-slate-800">{status.agent}</p>
            <p className="text-xs text-slate-500">{status.detail ?? status.status}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
