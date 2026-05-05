import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReportView } from "./ReportView";
import type { ResumeTailoringArtifacts, WorkflowSummary } from "../types";

const resumeArtifacts: ResumeTailoringArtifacts = {
  matchAssessment: {
    assessment_id: "match-1",
    recommendation: "strong-fit",
    strengths: [{ title: "Python", evidence_refs: ["ev-1"] }],
    gaps: [{ title: "Distributed systems", severity: "medium" }],
    risks: [{ title: "No production scale", severity: "medium" }],
    dimension_scores: { skills: 82 },
  },
  tailorPlan: {
    tailor_plan_id: "plan-1",
    target_role: "Backend Intern",
    headline_suggestion: "Backend engineer with Python and data infra focus",
    keyword_coverage: {
      covered: ["python"],
      missing: ["distributed systems"],
      overused: [],
    },
    section_actions: [
      {
        section: "experience",
        action: "rewrite",
        instruction: "Bring the API project to the top.",
        allowed_evidence_refs: ["ev-1"],
      },
    ],
    risk_notes: ["Do not overstate system scale."],
  },
  resumeVersion: {
    version_label: "backend-v1",
    summary_text: "Tailored summary",
    project_bullets: ["Built an internal API service."],
    keyword_insertions: ["Python"],
    omissions: ["Unrelated design work"],
    fact_check_status: "passed",
  },
  factCheckReport: {
    status: "passed",
    blocked_claims: [],
    checked_rules: ["no fabricated metrics"],
    issues: [],
    created_at: "2026-04-20T00:00:10Z",
  },
};

const workflowSummary: WorkflowSummary = {
  workflow_status: "verifier-approved",
  completed_steps: ["MatchingAgent", "ResumeTailorAgent", "ResumeVersionGenerator", "VerifierAgent"],
  pending_steps: [],
  next_recommended_action: "当前版本已通过校验，可以用于投递或面试准备。",
};

describe("ReportView", () => {
  it("renders the workflow summary and hydrated tailoring artifacts", () => {
    render(
      <ReportView
        reportMarkdown={
          "# Tailored Resume\n\n## 核心判断\n内容\n\n## 附：证据来源\n| 证据类别 | 链接 |\n| --- | --- |\n| JD | source |\n| Interview | source-2 |"
        }
        isLoading={false}
        reportMode="ready"
        reportNotice={null}
        reportStatusDetail="Report ready."
        resumeArtifacts={resumeArtifacts}
        workflowSummary={workflowSummary}
      />
    );

    expect(screen.getByText("Resume Tailor workflow summary")).toBeInTheDocument();
    expect(screen.getByText("verifier-approved")).toBeInTheDocument();
    expect(screen.getByText("当前版本已通过校验，可以用于投递或面试准备。")).toBeInTheDocument();
    expect(screen.getByText("MatchingAgent")).toBeInTheDocument();
    expect(screen.getByText("plan-1")).toBeInTheDocument();
    expect(screen.getByText("backend-v1")).toBeInTheDocument();
    expect(screen.getByText("Tailored summary")).toBeInTheDocument();
    expect(screen.getByText("no fabricated metrics")).toBeInTheDocument();
    expect(screen.getAllByText("2")).toHaveLength(2);
  });
});
