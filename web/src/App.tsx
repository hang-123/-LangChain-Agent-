import type { FormEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { ChatPanel } from "./components/ChatPanel";
import { ReportView } from "./components/ReportView";
import { useAgentStream } from "./hooks/useAgentStream";
import type { ResearchSessionInput } from "./types";

const quickPrompts = [
  "候选人画像 cand_001 + 简历证据 + 字节跳动后端实习 JD，请先出匹配分析，再给 Resume Tailor 计划。",
  "我有一份简历和目标岗位，请按 wf_resume_tailor_v2 输出改写计划、简历版本和事实校验。",
  "基于 CandidateProfile、ResumeEvidence、JobPosting 和 MatchAssessment，生成一版可审计的岗位定制简历。",
];


function parseResumeTailorInput(rawText: string): ResearchSessionInput {
  const trimmed = rawText.trim();
  if (!trimmed) {
    return { query: "" };
  }

  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed) as Record<string, unknown>;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        const query = typeof parsed.query === "string" ? parsed.query.trim() : trimmed;
        const input: ResearchSessionInput = { query };
        if (parsed.candidate_profile && typeof parsed.candidate_profile === "object" && !Array.isArray(parsed.candidate_profile)) {
          input.candidate_profile = parsed.candidate_profile as Record<string, unknown>;
        }
        if (Array.isArray(parsed.resume_evidence)) {
          input.resume_evidence = parsed.resume_evidence as Record<string, unknown>[];
        }
        if (parsed.job_posting && typeof parsed.job_posting === "object" && !Array.isArray(parsed.job_posting)) {
          input.job_posting = parsed.job_posting as Record<string, unknown>;
        }
        if (parsed.match_assessment && typeof parsed.match_assessment === "object" && !Array.isArray(parsed.match_assessment)) {
          input.match_assessment = parsed.match_assessment as Record<string, unknown>;
        }
        return input;
      }
    } catch {
      // Fall through to the freeform query path.
    }
  }

  return { query: trimmed };
}


export default function App() {
  const {
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
  } = useAgentStream();
  const [queryDraft, setQueryDraft] = useState("");
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus();
    }
  }, [isLoading]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!queryDraft.trim() || isLoading) {
      return;
    }
    const nextQuery = queryDraft.trim();
    setQueryDraft("");
    await sendQuery(parseResumeTailorInput(nextQuery));
  };

  return (
    <div className="min-h-screen px-4 py-5 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <header className="hero-panel overflow-hidden rounded-[36px] border border-white/70 p-6 sm:p-8">
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_320px]">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-slate-500">
                Resume Tailor Workflow
              </p>
              <h1 className="mt-4 max-w-4xl text-4xl font-semibold leading-tight text-slate-950 sm:text-5xl">
                把匹配分析、简历改写和事实校验串成一次可恢复的求职工作流
              </h1>
              <p className="mt-4 max-w-3xl text-base leading-8 text-slate-700">
                这不是泛化深研助手，而是围绕 `wf_resume_tailor_v2` 的单次工作流工具。请尽量把
                CandidateProfile、ResumeEvidence、JobPosting 和 MatchAssessment 一起提供进来，系统会先做匹配，
                再生成简历改写计划、岗位版本和事实校验结果。
              </p>

              <form onSubmit={handleSubmit} className="mt-8">
                <label className="sr-only" htmlFor="query-input">
                  Resume Tailor 工作流输入
                </label>
                <textarea
                  id="query-input"
                  ref={inputRef}
                  rows={4}
                  value={queryDraft}
                  onChange={(event) => setQueryDraft(event.target.value)}
                  disabled={isLoading}
                  placeholder="输入自然语言，或直接粘贴 JSON：{ query, candidate_profile, resume_evidence, job_posting, match_assessment }"
                  className="min-h-[148px] w-full rounded-[28px] border border-slate-200 bg-white/88 px-5 py-4 text-base leading-7 text-slate-900 shadow-[inset_0_1px_1px_rgba(15,23,42,0.04)] outline-none transition placeholder:text-slate-400 focus:border-[#c96c2d] focus:ring-4 focus:ring-[#c96c2d]/10 disabled:cursor-not-allowed disabled:bg-stone-100"
                />

                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <button
                    type="submit"
                    disabled={!queryDraft.trim() || isLoading}
                    className="rounded-full border border-transparent bg-[linear-gradient(135deg,#c96c2d,#1f5e77)] px-6 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isLoading ? "正在生成工作流..." : "开始 Resume Tailor"}
                  </button>
                  <button
                    type="button"
                    onClick={reset}
                    disabled={isLoading && logs.length === 0}
                    className="rounded-full border border-slate-300 bg-white/82 px-6 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    单次重置
                  </button>
                </div>
              </form>

              <div className="mt-5 flex flex-wrap gap-2">
                {quickPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    disabled={isLoading}
                    onClick={() => setQueryDraft(prompt)}
                    className="rounded-full border border-white/80 bg-white/72 px-4 py-2 text-xs font-medium text-slate-700 transition hover:border-[#1f5e77]/30 hover:bg-white"
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              {error && (
                <div className="mt-5 rounded-[24px] border border-rose-200 bg-rose-50/90 px-5 py-4 text-sm leading-6 text-rose-700">
                  {error}
                </div>
              )}
            </div>

            <aside className="grid gap-3">
              <div className="rounded-[28px] border border-white/70 bg-white/82 p-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                  Workflow Contract
                </p>
                <h2 className="mt-3 text-xl font-semibold text-slate-950">
                  MatchingAgent → ResumeTailorAgent → ResumeVersionGenerator → VerifierAgent
                </h2>
                <p className="mt-3 text-sm leading-7 text-slate-600">
                  先补齐候选人画像和简历证据，再生成匹配分析、改写计划和简历版本；事实校验通过后才建议进入投递。
                </p>
              </div>

              <div className="rounded-[28px] border border-white/70 bg-white/82 p-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                  Workflow Inputs
                </p>
                <ul className="mt-3 space-y-3 text-sm leading-7 text-slate-600">
                  <li>CandidateProfile: 目标角色、技能、教育和约束。</li>
                  <li>ResumeEvidence: 原始简历里的项目、实习和技能证据。</li>
                  <li>JobPosting / JobRequirements: 目标岗位和 must_have 要求。</li>
                  <li>MatchAssessment: 先验匹配结论，决定改写重点和风险边界。</li>
                </ul>
              </div>
            </aside>
          </div>
        </header>

        <main className="grid gap-5 lg:grid-cols-[420px_minmax(0,1fr)]">
          <ChatPanel logs={logs} agentStatuses={agentStatuses} isLoading={isLoading} maxRetries={maxRetries} />
          <ReportView
            reportMarkdown={reportMarkdown}
            isLoading={isLoading}
            reportMode={reportMode}
            reportNotice={reportNotice}
            reportStatusDetail={reportStatusDetail}
            resumeArtifacts={resumeArtifacts}
            workflowSummary={workflowSummary}
          />
        </main>
      </div>
    </div>
  );
}
