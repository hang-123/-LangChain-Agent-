import clsx from "clsx";
import type { AgentStatus } from "../types";
import { AGENT_LABELS } from "../lib/agentMeta";

const statusConfig: Record<
  AgentStatus["status"],
  { color: string; icon: string; bgColor: string }
> = {
  idle: {
    color: "text-slate-500",
    icon: "○",
    bgColor: "bg-slate-100",
  },
  running: {
    color: "text-blue-600",
    icon: "⟳",
    bgColor: "bg-blue-100",
  },
  done: {
    color: "text-green-600",
    icon: "✓",
    bgColor: "bg-green-100",
  },
  error: {
    color: "text-rose-600",
    icon: "!",
    bgColor: "bg-rose-100",
  },
};

interface Props {
  statuses: AgentStatus[];
}

export function AgentStatusPanel({ statuses }: Props) {
  return (
    <div className="space-y-3">
      {statuses.map((status) => {
        const config = statusConfig[status.status];
        const label = AGENT_LABELS[status.agent] ?? status.agent;

        return (
          <div
            key={status.agent}
            className={clsx(
              "flex items-center gap-3 p-3 rounded-lg transition-all",
              config.bgColor
            )}
          >
            <div
              className={clsx(
                "w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm",
                config.bgColor,
                config.color,
                status.status === "running" && "animate-spin"
              )}
            >
              {config.icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className={clsx("font-medium text-sm", config.color)}>
                {label}
              </div>
              <div className="text-xs text-slate-600 truncate">
                {status.detail ?? status.status}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

