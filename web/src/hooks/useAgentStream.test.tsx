import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { streamResearchSession } from "../lib/api";
import { useAgentStream } from "./useAgentStream";

vi.mock("../lib/api", () => ({
  streamResearchSession: vi.fn(),
}));

const mockedStreamResearchSession = vi.mocked(streamResearchSession);

describe("useAgentStream", () => {
  beforeEach(() => {
    mockedStreamResearchSession.mockReset();
  });

  it("hydrates artifacts from the done event and marks the workflow verifier-approved", async () => {
    mockedStreamResearchSession.mockImplementation(async (_input, onEvent) => {
      onEvent({
        type: "meta",
        run_id: "run-1",
        query: "resume tailor",
        max_retries: 3,
        started_at: "2026-04-20T00:00:00Z",
        timestamp: "2026-04-20T00:00:00Z",
      });
      onEvent({
        type: "done",
        run_id: "run-1",
        node: "ReportAgent",
        timestamp: "2026-04-20T00:00:10Z",
        report_markdown: "# Tailored Resume\n\n## 附：证据来源\n| 来源 | 链接 |\n| --- | --- |\n| JD | source |",
        resume_artifacts: {
          match_assessment: {
            assessment_id: "match-1",
            recommendation: "strong-fit",
          },
          tailor_plan: {
            tailor_plan_id: "plan-1",
            target_role: "Backend Intern",
          },
          resume_version: {
            version_label: "backend-v1",
            fact_check_status: "passed",
          },
          fact_check_report: {
            status: "passed",
            blocked_claims: [],
          },
        },
      });
    });

    const { result } = renderHook(() => useAgentStream());

    await act(async () => {
      await result.current.sendQuery({ query: "resume tailor" });
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.reportMarkdown).toContain("Tailored Resume");
    expect(result.current.resumeArtifacts.matchAssessment?.assessment_id).toBe("match-1");
    expect(result.current.resumeArtifacts.tailorPlan?.tailor_plan_id).toBe("plan-1");
    expect(result.current.resumeArtifacts.resumeVersion?.version_label).toBe("backend-v1");
    expect(result.current.workflowSummary.workflow_status).toBe("verifier-approved");
    expect(result.current.workflowSummary.completed_steps).toEqual([
      "MatchingAgent",
      "ResumeTailorAgent",
      "ResumeVersionGenerator",
      "VerifierAgent",
    ]);
    expect(result.current.workflowSummary.pending_steps).toEqual([]);
  });

  it("falls back to a recoverable state when the SSE transport reports an error", async () => {
    mockedStreamResearchSession.mockImplementation(async (_input, _onEvent, onError) => {
      onError("SSE 连接建立失败：响应体为空。");
    });

    const { result } = renderHook(() => useAgentStream());

    await act(async () => {
      await result.current.sendQuery({ query: "resume tailor" });
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBe("SSE 连接建立失败：响应体为空。");
    expect(result.current.workflowSummary.workflow_status).toBe("recoverable");
    expect(result.current.logs.some((entry) => entry.title === "网络错误")).toBe(true);
  });

  it("switches to fallback mode and keeps recovery guidance when the stream emits an error event", async () => {
    mockedStreamResearchSession.mockImplementation(async (_input, onEvent) => {
      onEvent({
        type: "error",
        run_id: "run-1",
        node: "ReportAgent",
        timestamp: "2026-04-20T00:00:10Z",
        detail: "VerifierAgent interrupted the run.",
      });
    });

    const { result } = renderHook(() => useAgentStream());

    await act(async () => {
      await result.current.sendQuery({ query: "resume tailor" });
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.reportMode).toBe("fallback");
    expect(result.current.reportNotice?.title).toBe("研究流程已中断");
    expect(result.current.workflowSummary.workflow_status).toBe("recoverable");
    expect(result.current.workflowSummary.next_recommended_action).toContain("修复当前中断点");
  });
});
