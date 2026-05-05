import { useRef, useState } from "react";

import { AGENT_FLOW, AGENT_LABELS } from "../lib/agentMeta";
import { streamResearchSession } from "../lib/api";
import type {
  AgentName,
  AgentStatus,
  ReportRenderMode,
  ResearchSessionInput,
  ResumeTailoringArtifacts,
  ResearchStreamEvent,
  StreamLogEntry,
  WorkflowSummary,
  UiNotice,
} from "../types";


function buildInitialStatuses(): AgentStatus[] {
  return AGENT_FLOW.map((agent) => ({
    agent,
    status: "idle",
    detail: "等待执行",
    retryCount: 0,
  }));
}


function createLogEntry(entry: Omit<StreamLogEntry, "id">): StreamLogEntry {
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return { id, ...entry };
}


function buildEmptyResumeArtifacts(): ResumeTailoringArtifacts {
  return {
    matchAssessment: null,
    tailorPlan: null,
    resumeVersion: null,
    factCheckReport: null,
  };
}


function pickResumeArtifacts(event: ResearchStreamEvent): ResumeTailoringArtifacts | null {
  if (event.type !== "done") {
    return null;
  }

  const embeddedArtifacts = event.resume_artifacts ?? event.resume_tailoring ?? null;
  const matchAssessment = event.match_assessment ?? embeddedArtifacts?.match_assessment ?? null;
  const tailorPlan = event.tailor_plan ?? embeddedArtifacts?.tailor_plan ?? null;
  const resumeVersion = event.resume_version ?? embeddedArtifacts?.resume_version ?? null;
  const factCheckReport = event.fact_check_report ?? embeddedArtifacts?.fact_check_report ?? null;

  if (!matchAssessment && !tailorPlan && !resumeVersion && !factCheckReport) {
    return null;
  }

  return {
    matchAssessment,
    tailorPlan,
    resumeVersion,
    factCheckReport,
  };
}


function buildWorkflowSummary({
  isLoading,
  reportMarkdown,
  reportNotice,
  resumeArtifacts,
}: {
  isLoading: boolean;
  reportMarkdown: string;
  reportNotice: UiNotice | null;
  resumeArtifacts: ResumeTailoringArtifacts;
}): WorkflowSummary {
  const completedSteps: string[] = [];
  const pendingSteps: string[] = [];

  if (resumeArtifacts.matchAssessment) {
    completedSteps.push("MatchingAgent");
  } else {
    pendingSteps.push("MatchingAgent");
  }

  if (resumeArtifacts.tailorPlan) {
    completedSteps.push("ResumeTailorAgent");
  } else {
    pendingSteps.push("ResumeTailorAgent");
  }

  if (resumeArtifacts.resumeVersion) {
    completedSteps.push("ResumeVersionGenerator");
  } else {
    pendingSteps.push("ResumeVersionGenerator");
  }

  if (resumeArtifacts.factCheckReport?.status === "passed") {
    completedSteps.push("VerifierAgent");
  } else {
    pendingSteps.push("VerifierAgent");
  }

  const workflowStatus: WorkflowSummary["workflow_status"] =
    reportNotice?.level === "error"
      ? "recoverable"
      : resumeArtifacts.factCheckReport?.status === "passed"
      ? "verifier-approved"
      : isLoading
      ? "running"
      : reportMarkdown.trim()
      ? "completed"
      : "recoverable";

  let nextRecommendedAction = "继续检查结构化输入是否完整。";
  if (workflowStatus === "recoverable") {
    nextRecommendedAction = "先修复当前中断点，再从最近的成功步骤继续恢复。";
  } else if (pendingSteps.includes("MatchingAgent")) {
    nextRecommendedAction = "先补齐候选人画像、简历证据和目标岗位，再生成匹配分析。";
  } else if (pendingSteps.includes("ResumeTailorAgent")) {
    nextRecommendedAction = "继续生成简历改写计划。";
  } else if (pendingSteps.includes("ResumeVersionGenerator")) {
    nextRecommendedAction = "继续生成岗位定制简历版本。";
  } else if (pendingSteps.includes("VerifierAgent")) {
    nextRecommendedAction = "等待 VerifierAgent 完成事实校验后再交付。";
  } else if (workflowStatus === "verifier-approved") {
    nextRecommendedAction = "当前版本已通过校验，可以用于投递或面试准备。";
  } else if (workflowStatus === "completed") {
    nextRecommendedAction = "当前工作流已完成，可以回看报告和结构化产物。";
  }

  return {
    workflow_status: workflowStatus,
    completed_steps: completedSteps,
    pending_steps: pendingSteps,
    next_recommended_action: nextRecommendedAction,
  };
}


export function useAgentStream() {
  const abortRef = useRef<AbortController | null>(null);
  const [logs, setLogs] = useState<StreamLogEntry[]>([]);
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>(buildInitialStatuses);
  const [resumeArtifacts, setResumeArtifacts] = useState<ResumeTailoringArtifacts>(buildEmptyResumeArtifacts);
  const [reportMarkdown, setReportMarkdown] = useState("");
  const [reportMode, setReportMode] = useState<ReportRenderMode>("waiting");
  const [reportNotice, setReportNotice] = useState<UiNotice | null>(null);
  const [reportStatusDetail, setReportStatusDetail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [maxRetries, setMaxRetries] = useState(3);
  const runIdRef = useRef<string>("");

  const appendLog = (entry: Omit<StreamLogEntry, "id">) => {
    setLogs((prev) => [...prev, createLogEntry(entry)]);
  };

  const reset = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLogs([]);
    setAgentStatuses(buildInitialStatuses());
    setResumeArtifacts(buildEmptyResumeArtifacts());
    setReportMarkdown("");
    setReportMode("waiting");
    setReportNotice(null);
    setReportStatusDetail("");
    setError(null);
    setIsLoading(false);
    setMaxRetries(3);
    runIdRef.current = "";
  };

  const setFallbackNotice = (detail?: string) => {
    const message =
      detail && detail.trim()
        ? detail
        : "ReportAgent 当前展示的是 renderer-first 版本；即使局部润色不可用，也不会影响报告结构、规则和证据展示。";
    setReportNotice({
      level: "warning",
      title: "ReportAgent 已切到纯渲染模式",
      message,
      hints: [
        "报告结构、章节顺序和证据表由 renderer 控制，不依赖整篇 prompt 成稿。",
        "如果你希望启用局部润色，再确认后端环境里已安装 `langchain-openai`，并且模型配置可用。",
        "即使没有 LLM，本轮报告也应保持可读和可追溯，只是语言会更直接。",
      ],
    });
  };

  const workflowSummary = buildWorkflowSummary({
    isLoading,
    reportMarkdown,
    reportNotice,
    resumeArtifacts,
  });

  const updateStatus = (
    agent: AgentName,
    status: AgentStatus["status"],
    detail: string,
    retryCount: number = 0
  ) => {
    setAgentStatuses((prev) =>
      prev.map((item) =>
        item.agent === agent ? { ...item, status, detail, retryCount } : item
      )
    );
  };

  const handleEvent = (event: ResearchStreamEvent) => {
    const timestamp = new Date().toISOString();

    if (event.type === "meta") {
      runIdRef.current = event.run_id;
      setMaxRetries(event.max_retries);
      return;
    }

    if (event.type === "status") {
      if (event.agent === "ReportAgent" && event.phase === "started") {
        setReportMarkdown("");
        setReportMode("streaming");
        setReportStatusDetail(event.detail);
        setReportNotice(null);
      }

      if (event.agent === "ReportAgent" && event.phase === "completed") {
        setReportStatusDetail(event.detail);
        if (event.detail.includes("LLM 不可用")) {
          setReportMode("fallback");
          setFallbackNotice(event.detail);
        } else if (event.detail.trim()) {
          setReportMode((prev) => (prev === "fallback" ? prev : "ready"));
        }
      }

      updateStatus(
        event.agent,
        event.phase === "completed" ? "done" : "running",
        event.detail,
        event.retry_count ?? 0
      );

      appendLog({
        kind: "status",
        agent: event.agent,
        title: `${AGENT_LABELS[event.agent]} · ${event.phase === "completed" ? "完成" : "启动"}`,
        content: event.detail,
        runId: event.run_id,
        node: event.node,
        metadata: null,
        timestamp,
      });
      return;
    }

    if (event.type === "chunk") {
      setReportMode("streaming");
      setReportMarkdown((prev) => prev + event.content);
      return;
    }

    if (event.type === "message") {
      const speaker = event.speaker ?? "System";
      if (speaker === "ReportAgent") {
        const fallbackReport = Boolean(event.metadata && event.metadata["fallback_report"]);
        if (fallbackReport) {
          setReportMode("fallback");
          setFallbackNotice(
            typeof event.metadata?.status === "string" ? event.metadata.status : undefined
          );
        }
      }
      appendLog({
        kind: "message",
        agent: speaker,
        title: AGENT_LABELS[speaker] ?? speaker,
        content: event.content,
        runId: event.run_id,
        node: event.node,
        metadata: event.metadata ?? null,
        timestamp: event.timestamp ?? timestamp,
      });
      return;
    }

    if (event.type === "done") {
      const nextResumeArtifacts = pickResumeArtifacts(event);
      if (nextResumeArtifacts) {
        setResumeArtifacts(nextResumeArtifacts);
      }
      const qualityMode = typeof event.quality_summary?.["quality_mode"] === "string"
        ? String(event.quality_summary?.["quality_mode"])
        : "";
      if (event.report_markdown) {
        const finalMarkdown = event.report_markdown;
        setReportMarkdown(finalMarkdown);
        setReportMode((prev) => {
          if (prev === "fallback") {
            return "fallback";
          }
          if (qualityMode === "conservative") {
            return "conservative";
          }
          return finalMarkdown.trim() ? "ready" : "waiting";
        });
        if (finalMarkdown.includes("⚠️ 系统已尽最大努力生成")) {
          setReportNotice((prev) =>
            prev ?? {
              level: "warning",
              title: "报告已触发熔断返回",
              message: "ReviewAgent 在最大重试次数内仍未完全通过审查，当前展示的是最终调优版本。",
              hints: ["可以先查看左侧 ReviewAgent 日志，确认问题是公司特异性、证据归因还是排版结构。"],
            }
          );
        }
        if (qualityMode === "fallback") {
          setFallbackNotice(
            typeof event.quality_summary?.["warning_message"] === "string"
              ? String(event.quality_summary?.["warning_message"])
              : undefined
          );
        }
      }
      setIsLoading(false);
      return;
    }

    if (event.type === "error") {
      setError(event.detail);
      setReportMode("fallback");
      setReportNotice({
        level: "error",
        title: "研究流程已中断",
        message: event.detail,
        hints: [
          "先检查后端终端日志，确认是模型调用、SSE 中断还是接口异常。",
          "如果只是偶发网络问题，可以直接重新发起一次请求。",
        ],
      });
      setIsLoading(false);
      setAgentStatuses((prev) =>
        prev.map((item) =>
          item.status === "running" ? { ...item, status: "error", detail: "执行中断" } : item
        )
      );
      appendLog({
        kind: "error",
        agent: "System",
        title: "系统错误",
        content: event.detail,
        runId: event.run_id,
        node: event.node,
        metadata: null,
        timestamp,
      });
    }
  };

  const sendQuery = async (input: ResearchSessionInput | string) => {
    const normalizedInput: ResearchSessionInput =
      typeof input === "string"
        ? { query: input.trim() }
        : {
            ...input,
            query: input.query.trim(),
          };
    const cleanQuery = normalizedInput.query.trim();
    if (!cleanQuery) {
      return;
    }

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setLogs([]);
    setAgentStatuses(buildInitialStatuses());
    setResumeArtifacts(buildEmptyResumeArtifacts());
    setReportMarkdown("");
    setReportMode("waiting");
    setReportNotice(null);
    setReportStatusDetail("");
    setError(null);
    setIsLoading(true);
    runIdRef.current = "";

    appendLog({
      kind: "user",
      agent: "User",
      title: "本次研究任务",
      content: cleanQuery,
      runId: runIdRef.current,
      metadata: null,
      timestamp: new Date().toISOString(),
    });

    try {
      await streamResearchSession(
        normalizedInput,
        handleEvent,
        (message) => {
          setError(message);
          setIsLoading(false);
          appendLog({
            kind: "error",
            agent: "System",
            title: "网络错误",
            content: message,
            runId: runIdRef.current,
            metadata: null,
            timestamp: new Date().toISOString(),
          });
        },
        abortRef.current.signal
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }
      const message = error instanceof Error ? error.message : "SSE 流读取失败。";
      setError(message);
      appendLog({
        kind: "error",
        agent: "System",
        title: "系统错误",
        content: message,
        runId: runIdRef.current,
        metadata: null,
        timestamp: new Date().toISOString(),
      });
    } finally {
      setIsLoading(false);
    }
  };

  return {
    logs,
    agentStatuses,
    reportMarkdown,
    reportMode,
    reportNotice,
    reportStatusDetail,
    resumeArtifacts,
    workflowSummary,
    error,
    isLoading,
    maxRetries,
    reset,
    sendQuery,
  };
}
