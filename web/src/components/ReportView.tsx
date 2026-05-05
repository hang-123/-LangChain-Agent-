import { useState } from "react";
import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type {
  FactCheckReportArtifact,
  MatchAssessmentArtifact,
  ReportRenderMode,
  ResumeTailoringArtifacts,
  TailorPlanArtifact,
  UiNotice,
  WorkflowSummary,
} from "../types";


function downloadMarkdown(content: string, title: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${title || "career-research-report"}.md`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}


function summarizeReportMarkdown(reportMarkdown: string): { sectionCount: number; evidenceCount: number } {
  const lines = reportMarkdown.split(/\r?\n/);
  let sectionCount = 0;
  let evidenceCount = 0;
  let inEvidenceSection = false;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      continue;
    }

    if (line.startsWith("## ")) {
      sectionCount += 1;
      inEvidenceSection = line === "## 附：证据来源";
      continue;
    }

    if (!inEvidenceSection) {
      continue;
    }

    if (line.startsWith("|") && !line.startsWith("| ---") && !line.startsWith("| 证据类别 |")) {
      evidenceCount += 1;
    }
  }

  return { sectionCount, evidenceCount };
}


function compactStrings(values?: Array<string | undefined | null> | null): string[] {
  return (values ?? []).filter((value): value is string => Boolean(value && value.trim()));
}


function formatRecord(record?: Record<string, number> | null): string[] {
  if (!record) {
    return [];
  }

  return Object.entries(record)
    .filter(([, value]) => Number.isFinite(value))
    .map(([key, value]) => `${key}: ${value}`);
}


function hasResumeArtifacts(artifacts: ResumeTailoringArtifacts): boolean {
  return Boolean(
    artifacts.matchAssessment || artifacts.tailorPlan || artifacts.resumeVersion || artifacts.factCheckReport
  );
}


function getArtifactTone(status: "ready" | "loading" | "missing" | "error") {
  if (status === "ready") {
    return "border-emerald-200 bg-emerald-50/80 text-emerald-900";
  }
  if (status === "error") {
    return "border-rose-200 bg-rose-50/80 text-rose-800";
  }
  if (status === "loading") {
    return "border-amber-200 bg-amber-50/80 text-amber-900";
  }
  return "border-slate-200 bg-white/70 text-slate-600";
}


function getWorkflowTone(status: WorkflowSummary["workflow_status"]) {
  if (status === "verifier-approved") {
    return "border-emerald-200 bg-emerald-50 text-emerald-900";
  }
  if (status === "completed") {
    return "border-sky-200 bg-sky-50 text-sky-900";
  }
  if (status === "recoverable") {
    return "border-amber-200 bg-amber-50 text-amber-900";
  }
  return "border-slate-200 bg-white text-slate-700";
}


function ArtifactPanel({
  title,
  subtitle,
  status,
  children,
}: {
  title: string;
  subtitle: string;
  status: "ready" | "loading" | "missing" | "error";
  children: ReactNode;
}) {
  return (
    <section className="rounded-[24px] border border-slate-200 bg-white/80 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">{title}</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">{subtitle}</p>
        </div>
        <span
          className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${getArtifactTone(
            status
          )}`}
        >
          {status === "ready" ? "Ready" : status === "loading" ? "Loading" : status === "error" ? "Error" : "Empty"}
        </span>
      </div>
      <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700">{children}</div>
    </section>
  );
}


function ItemList({ items, emptyLabel }: { items: string[]; emptyLabel: string }) {
  if (items.length === 0) {
    return <p className="text-sm leading-6 text-slate-500">{emptyLabel}</p>;
  }

  return (
    <ul className="space-y-2">
      {items.map((item, index) => (
        <li key={`${item}-${index}`} className="rounded-2xl border border-slate-200 bg-stone-50 px-3 py-2">
          {item}
        </li>
      ))}
    </ul>
  );
}


function MatchAssessmentPanel({
  artifact,
  isLoading,
  hasError,
}: {
  artifact: MatchAssessmentArtifact | null;
  isLoading: boolean;
  hasError: boolean;
}) {
  const status = artifact ? "ready" : hasError ? "error" : isLoading ? "loading" : "missing";
  const strengths = (artifact?.strengths ?? []).slice(0, 3).map((item) => {
    const refs = compactStrings(item?.evidence_refs);
    return `${item?.title ?? "未命名优势"}${refs.length > 0 ? ` · ${refs.join(", ")}` : ""}`;
  });
  const gaps = (artifact?.gaps ?? []).slice(0, 3).map((item) => {
    const severity = item?.severity ? ` · ${item.severity}` : "";
    return `${item?.title ?? "未命名缺口"}${severity}`;
  });
  const risks = (artifact?.risks ?? []).slice(0, 3).map((item) => {
    const severity = item?.severity ? ` · ${item.severity}` : "";
    return `${item?.title ?? "未命名风险"}${severity}`;
  });
  const scores = formatRecord(artifact?.dimension_scores ?? null).slice(0, 6);

  return (
    <ArtifactPanel
      title="Match Assessment"
      subtitle="岗位匹配的结构化结论，保留优势、缺口、风险和维度分数。"
      status={status}
    >
      {artifact ? (
        <>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Assessment ID</div>
              <div className="mt-1 break-all text-sm text-slate-900">{artifact.assessment_id ?? "未提供"}</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Recommendation</div>
              <div className="mt-1 text-sm text-slate-900">{artifact.recommendation ?? "未提供"}</div>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Overall Score</div>
              <div className="mt-1 text-sm text-slate-900">{artifact.overall_score ?? "未提供"}</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Job ID</div>
              <div className="mt-1 break-all text-sm text-slate-900">{artifact.job_id ?? "未提供"}</div>
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Strengths</div>
            <ItemList items={strengths} emptyLabel={isLoading ? "等待后端返回优势摘要。" : "当前 run 未返回优势摘要。"} />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Gaps</div>
            <ItemList items={gaps} emptyLabel={isLoading ? "等待后端返回差距摘要。" : "当前 run 未返回差距摘要。"} />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Risks</div>
            <ItemList items={risks} emptyLabel={isLoading ? "等待后端返回风险提示。" : "当前 run 未返回风险提示。"} />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Dimension Scores</div>
            <ItemList items={scores} emptyLabel={isLoading ? "等待后端返回维度分数。" : "当前 run 未返回维度分数。"} />
          </div>
        </>
      ) : hasError ? (
        <p className="text-sm leading-6 text-rose-700">本次 run 中断，无法生成匹配结论。</p>
      ) : isLoading ? (
        <p className="text-sm leading-6 text-slate-500">正在等待匹配结果。</p>
      ) : (
        <p className="text-sm leading-6 text-slate-500">当前 run 还没有返回匹配结论。</p>
      )}
    </ArtifactPanel>
  );
}


function TailorPlanPanel({
  artifact,
  isLoading,
  hasError,
}: {
  artifact: TailorPlanArtifact | null;
  isLoading: boolean;
  hasError: boolean;
}) {
  const status = artifact ? "ready" : hasError ? "error" : isLoading ? "loading" : "missing";
  const coverage = artifact?.keyword_coverage;
  const actions = (artifact?.section_actions ?? []).slice(0, 3).map((item) => {
    const refs = compactStrings(item?.allowed_evidence_refs);
    return `${item?.section ?? "unknown"} · ${item?.action ?? "rewrite"} · ${item?.instruction ?? "未提供"}${
      refs.length > 0 ? ` · ${refs.join(", ")}` : ""
    }`;
  });

  return (
    <ArtifactPanel
      title="Tailor Plan"
      subtitle="面向目标岗位的改写计划，只展示允许的表达调整与关键词覆盖。"
      status={status}
    >
      {artifact ? (
        <>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Tailor Plan ID</div>
              <div className="mt-1 break-all text-sm text-slate-900">{artifact.tailor_plan_id ?? "未提供"}</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Target Role</div>
              <div className="mt-1 text-sm text-slate-900">{artifact.target_role ?? "未提供"}</div>
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Headline Suggestion</div>
            <div className="mt-1 text-sm leading-6 text-slate-900">
              {artifact.headline_suggestion ?? "未提供"}
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Keyword Coverage</div>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
                <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Covered</div>
                <div className="mt-1 text-sm text-slate-900">
                  {compactStrings(coverage?.covered).join(" · ") || "未提供"}
                </div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
                <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Missing</div>
                <div className="mt-1 text-sm text-slate-900">
                  {compactStrings(coverage?.missing).join(" · ") || "未提供"}
                </div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
                <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Overused</div>
                <div className="mt-1 text-sm text-slate-900">
                  {compactStrings(coverage?.overused).join(" · ") || "未提供"}
                </div>
              </div>
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Section Actions</div>
            <ItemList items={actions} emptyLabel={isLoading ? "等待后端返回改写动作。" : "当前 run 未返回改写动作。"} />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Risk Notes</div>
            <ItemList items={compactStrings(artifact.risk_notes)} emptyLabel={isLoading ? "等待后端返回风险提示。" : "当前 run 未返回风险提示。"} />
          </div>
        </>
      ) : hasError ? (
        <p className="text-sm leading-6 text-rose-700">本次 run 中断，无法生成定制计划。</p>
      ) : isLoading ? (
        <p className="text-sm leading-6 text-slate-500">正在等待定制计划。</p>
      ) : (
        <p className="text-sm leading-6 text-slate-500">当前 run 还没有返回定制计划。</p>
      )}
    </ArtifactPanel>
  );
}


function ResumeVersionPanel({
  artifact,
  isLoading,
  hasError,
}: {
  artifact: ResumeTailoringArtifacts["resumeVersion"];
  isLoading: boolean;
  hasError: boolean;
}) {
  const status = artifact ? "ready" : hasError ? "error" : isLoading ? "loading" : "missing";

  return (
    <ArtifactPanel
      title="Resume Version"
      subtitle="面向目标岗位的简历版本摘要，突出可交付文本和事实校验状态。"
      status={status}
    >
      {artifact ? (
        <>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Version Label</div>
              <div className="mt-1 text-sm text-slate-900">{artifact.version_label ?? "未提供"}</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Fact Check Status</div>
              <div className="mt-1 text-sm text-slate-900">{artifact.fact_check_status ?? "未提供"}</div>
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white/70 px-3 py-2">
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Summary Text</div>
            <div className="mt-1 text-sm leading-6 text-slate-900">
              {artifact.summary_text ?? "未提供"}
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Project Bullets</div>
            <ItemList items={compactStrings(artifact.project_bullets)} emptyLabel={isLoading ? "等待后端返回项目表述。" : "当前 run 未返回项目表述。"} />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Keyword Insertions</div>
              <ItemList
                items={compactStrings(artifact.keyword_insertions)}
                emptyLabel={isLoading ? "等待后端返回关键词插入。" : "当前 run 未返回关键词插入。"}
              />
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Omissions</div>
              <ItemList items={compactStrings(artifact.omissions)} emptyLabel={isLoading ? "等待后端返回省略项。" : "当前 run 未返回省略项。"} />
            </div>
          </div>
        </>
      ) : hasError ? (
        <p className="text-sm leading-6 text-rose-700">本次 run 中断，无法生成简历版本。</p>
      ) : isLoading ? (
        <p className="text-sm leading-6 text-slate-500">正在等待简历版本。</p>
      ) : (
        <p className="text-sm leading-6 text-slate-500">当前 run 还没有返回简历版本。</p>
      )}
    </ArtifactPanel>
  );
}


function FactCheckPanel({
  artifact,
  isLoading,
  hasError,
}: {
  artifact: FactCheckReportArtifact | null;
  isLoading: boolean;
  hasError: boolean;
}) {
  const status = artifact ? "ready" : hasError ? "error" : isLoading ? "loading" : "missing";
  const blockedClaims = (artifact?.blocked_claims ?? []).slice(0, 4).map((item) =>
    typeof item === "string" ? item : `${item?.claim ?? "未命名声明"}${item?.reason ? ` · ${item.reason}` : ""}`
  );
  const stateTone =
    artifact?.status === "passed"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900"
      : artifact?.status
      ? "border-amber-200 bg-amber-50 text-amber-900"
      : "border-slate-200 bg-white text-slate-700";

  return (
    <ArtifactPanel
      title="Fact Check Report"
      subtitle="事实校验的放行结果与拦截项，帮助区分可写入和不可写入内容。"
      status={status}
    >
      {artifact ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${stateTone}`}>
              {artifact.status ?? "unknown"}
            </span>
            {artifact.created_at && <span className="text-xs text-slate-500">{artifact.created_at}</span>}
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Blocked Claims</div>
            <ItemList
              items={blockedClaims}
              emptyLabel={isLoading ? "等待后端返回被拦截声明。" : "当前 run 未返回被拦截声明。"}
            />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Checked Rules</div>
            <ItemList
              items={compactStrings(artifact.checked_rules)}
              emptyLabel={isLoading ? "等待后端返回校验规则。" : "当前 run 未返回校验规则。"}
            />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Issues</div>
            <ItemList items={compactStrings(artifact.issues)} emptyLabel={isLoading ? "等待后端返回问题项。" : "当前 run 未返回问题项。"} />
          </div>
        </>
      ) : hasError ? (
        <p className="text-sm leading-6 text-rose-700">本次 run 中断，无法生成事实校验报告。</p>
      ) : isLoading ? (
        <p className="text-sm leading-6 text-slate-500">正在等待事实校验结果。</p>
      ) : (
        <p className="text-sm leading-6 text-slate-500">当前 run 还没有返回事实校验报告。</p>
      )}
    </ArtifactPanel>
  );
}


export function ReportView({
  reportMarkdown,
  isLoading,
  reportMode,
  reportNotice,
  reportStatusDetail,
  resumeArtifacts,
  workflowSummary,
}: {
  reportMarkdown: string;
  isLoading: boolean;
  reportMode: ReportRenderMode;
  reportNotice: UiNotice | null;
  reportStatusDetail: string;
  resumeArtifacts: ResumeTailoringArtifacts;
  workflowSummary: WorkflowSummary;
}) {
  const [copied, setCopied] = useState(false);
  const [actionError, setActionError] = useState("");

  const { sectionCount, evidenceCount } = summarizeReportMarkdown(reportMarkdown);
  const titleMatch = reportMarkdown.match(/^#\s+(.*)$/m);
  const title = titleMatch?.[1] ?? "专属求职研究报告";
  const modeLabel =
    reportMode === "streaming"
      ? "Streaming"
      : reportMode === "fallback"
      ? "Fallback"
      : reportMode === "ready"
      ? "Ready"
      : "Waiting";
  const modeTone =
    reportMode === "fallback"
      ? "text-amber-900"
      : reportMode === "streaming"
      ? "text-sky-900"
      : "text-slate-950";
  const noticeClasses =
    reportNotice?.level === "error"
      ? "border-rose-200 bg-rose-50/95 text-rose-800"
      : reportNotice?.level === "warning"
      ? "border-amber-200 bg-amber-50/95 text-amber-900"
      : "border-sky-200 bg-sky-50/95 text-sky-800";
  const hasError = reportNotice?.level === "error";
  const artifactReady = hasResumeArtifacts(resumeArtifacts);
  const artifactStateLabel = hasError ? "Error" : isLoading ? "Loading" : artifactReady ? "Ready" : "Empty";

  const visibleCopied = copied && reportMode !== "waiting" && Boolean(reportMarkdown);
  const visibleActionError = reportMode === "waiting" || !reportMarkdown ? "" : actionError;

  const handleCopy = async () => {
    if (!reportMarkdown) {
      return;
    }

    try {
      await navigator.clipboard.writeText(reportMarkdown);
      setCopied(true);
      setActionError("");
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
      setActionError("复制失败，请检查浏览器剪贴板权限后重试。");
    }
  };

  const handleDownload = () => {
    if (!reportMarkdown) {
      return;
    }

    try {
      downloadMarkdown(reportMarkdown, title);
      setActionError("");
    } catch {
      setActionError("下载失败，请稍后重试。");
    }
  };

  return (
    <section className="glass-panel flex h-full min-h-[720px] flex-col overflow-hidden">
      <div className="border-b border-slate-200 px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-500">
              Final Deliverable
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <h2 className="text-2xl font-semibold text-slate-950">{title}</h2>
              <span
                className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${
                  reportMode === "fallback"
                    ? "border-amber-300 bg-amber-100 text-amber-900"
                    : reportMode === "streaming"
                    ? "border-sky-200 bg-sky-100 text-sky-900"
                    : "border-slate-200 bg-white text-slate-700"
                }`}
              >
                {modeLabel}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              ReportAgent 现在以结构化渲染为主，必要时只做局部语言润色；如果 Review 打回，这里会切换到最新一轮版本。
              {isLoading ? " 当前正在接收最新一轮成稿状态。" : " 当前展示的是最近一次完成的报告版本。"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleCopy}
              disabled={!reportMarkdown}
              className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {visibleCopied ? "已复制" : "复制全文"}
            </button>
            <button
              type="button"
              onClick={handleDownload}
              disabled={!reportMarkdown}
              className="rounded-full border border-transparent bg-[linear-gradient(135deg,#c96c2d,#1f5e77)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              下载 Markdown
            </button>
          </div>
        </div>

        {visibleActionError && (
          <p className="mt-3 rounded-2xl border border-rose-200 bg-rose-50/80 px-4 py-2 text-sm leading-6 text-rose-700">
            {visibleActionError}
          </p>
        )}

        {reportNotice && (
          <div className={`mt-5 rounded-[24px] border px-5 py-4 shadow-sm ${noticeClasses}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.28em] opacity-75">
                  {reportNotice.level === "error"
                    ? "System Alert"
                    : reportNotice.level === "warning"
                    ? "Report Warning"
                    : "System Notice"}
                </p>
                <h3 className="mt-2 text-lg font-semibold">{reportNotice.title}</h3>
                <p className="mt-2 text-sm leading-6">{reportNotice.message}</p>
              </div>
              <div className="rounded-2xl border border-current/15 bg-white/50 px-4 py-3 text-right">
                <div className="text-[11px] uppercase tracking-[0.24em] opacity-70">Render Mode</div>
                <div className={`mt-1 text-lg font-semibold ${modeTone}`}>{modeLabel}</div>
              </div>
            </div>
            {reportNotice.hints && reportNotice.hints.length > 0 && (
              <div className="mt-4 grid gap-2">
                {reportNotice.hints.map((hint) => (
                  <div
                    key={hint}
                    className="rounded-2xl border border-current/10 bg-white/55 px-4 py-3 text-sm leading-6"
                  >
                    {hint}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {reportStatusDetail && (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-white/70 px-4 py-3">
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Latest Report Status</div>
            <div className="mt-2 text-sm leading-6 text-slate-700">{reportStatusDetail}</div>
          </div>
        )}

        <div className="mt-4 rounded-[24px] border border-slate-200 bg-white/75 px-5 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                Workflow State
              </p>
              <h3 className="mt-2 text-lg font-semibold text-slate-950">Resume Tailor workflow summary</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {workflowSummary.next_recommended_action}
              </p>
            </div>
            <span
              className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${getWorkflowTone(
                workflowSummary.workflow_status
              )}`}
            >
              {workflowSummary.workflow_status}
            </span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Completed Steps</div>
              <ItemList items={workflowSummary.completed_steps} emptyLabel="当前还没有完成的工作流步骤。" />
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Pending Steps</div>
              <ItemList items={workflowSummary.pending_steps} emptyLabel="当前没有待办的工作流步骤。" />
            </div>
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white/80 px-4 py-3">
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Sections</div>
            <div className="mt-1 text-xl font-semibold text-slate-950">{sectionCount}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white/80 px-4 py-3">
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Evidence Links</div>
            <div className="mt-1 text-xl font-semibold text-slate-950">{evidenceCount}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white/80 px-4 py-3">
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Render Mode</div>
            <div className={`mt-1 text-xl font-semibold ${modeTone}`}>{modeLabel}</div>
          </div>
        </div>

        <section className="mt-5 rounded-[28px] border border-slate-200 bg-slate-50/70 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-500">
                Resume Tailoring Artifacts
              </p>
              <h3 className="mt-2 text-lg font-semibold text-slate-950">结构化简历交付物</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                这里直接展示岗位匹配、改写计划、简历版本和事实校验，避免把这些内容埋进 Markdown 报告里。
              </p>
            </div>
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${getArtifactTone(
              hasError ? "error" : isLoading ? "loading" : artifactReady ? "ready" : "missing"
            )}`}>
              {artifactStateLabel}
            </span>
          </div>
          <div className="mt-4 grid gap-4 xl:grid-cols-2">
            <MatchAssessmentPanel
              artifact={resumeArtifacts.matchAssessment}
              isLoading={isLoading}
              hasError={hasError}
            />
            <TailorPlanPanel
              artifact={resumeArtifacts.tailorPlan}
              isLoading={isLoading}
              hasError={hasError}
            />
            <ResumeVersionPanel
              artifact={resumeArtifacts.resumeVersion}
              isLoading={isLoading}
              hasError={hasError}
            />
            <FactCheckPanel
              artifact={resumeArtifacts.factCheckReport}
              isLoading={isLoading}
              hasError={hasError}
            />
          </div>
        </section>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
        {!reportMarkdown ? (
          <div className="flex h-full min-h-[420px] items-center justify-center rounded-[28px] border border-dashed border-slate-300 bg-white/55 p-10 text-center">
            <div className="max-w-xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-500">
                Waiting For Report
              </p>
              <h3 className="mt-3 text-2xl font-semibold text-slate-950">右侧会在 ReportAgent 出稿时实时打字渲染</h3>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                IntentRouter 先分流，SearchAgent 写入真实证据，ReportAgent 再依据结构化字段和渲染规则生成报告；
                如果 ReviewAgent 不满意，这里会自动切到最新重写版本。
              </p>
            </div>
          </div>
        ) : (
          <article className="report-markdown mx-auto max-w-4xl">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{reportMarkdown}</ReactMarkdown>
          </article>
        )}
      </div>
    </section>
  );
}
