from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.core.contracts import CaseEvaluation, EvalMetadata, EvalSuiteSummary, NodeScorecard, ResearchCase
from api.core.policy_loader import coerce_policy


CASE_PATH = Path(__file__).with_name("research_cases.json")


def load_research_cases() -> list[ResearchCase]:
    payload = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    return [ResearchCase.model_validate(item) for item in payload]


def _build_eval_metadata(case: ResearchCase, final_state: dict[str, Any]) -> EvalMetadata:
    manifest = dict(final_state.get("run_manifest") or {})
    return EvalMetadata(
        run_id=str(final_state.get("run_id") or manifest.get("run_id") or ""),
        case_id=case.case_id,
        prompt_version=str(manifest.get("prompt_version") or "unknown"),
        policy_version=str(manifest.get("policy_version") or "unknown"),
        code_version=str(manifest.get("code_version") or "unknown"),
        model_name=str(manifest.get("model_name") or "unknown"),
        experiment_id=str(manifest.get("experiment_id") or ""),
        variant=str(manifest.get("variant") or "control"),
    )


def _score_retrieval(case: ResearchCase, final_state: dict[str, Any]) -> tuple[int, list[str]]:
    policy = coerce_policy(final_state.get("policy"))
    retrieval_policy = policy.retrieval_policy
    insights = dict(final_state.get("insights") or {})
    diagnostics = dict(final_state.get("retrieval_diagnostics") or {})
    failures: list[str] = []
    score = 100

    evidence_count = int(insights.get("evidence_count") or 0)
    if evidence_count < max(case.minimum_evidence_count, retrieval_policy.min_evidence_count):
        failures.append(f"evidence_count below threshold: {evidence_count}")
        score -= 30

    company_specific_count = int(insights.get("company_specific_source_count") or 0)
    if company_specific_count < retrieval_policy.min_company_specific_sources:
        failures.append(f"company_specific_source_count below threshold: {company_specific_count}")
        score -= 20

    missing_classes = diagnostics.get("missing_classes") or []
    if isinstance(missing_classes, list) and missing_classes:
        failures.append(f"missing evidence classes: {', '.join(str(item) for item in missing_classes[:3])}")
        score -= min(30, len(missing_classes) * 10)

    return max(0, score), failures


def _score_attribution(final_state: dict[str, Any]) -> tuple[int, list[str]]:
    policy = coerce_policy(final_state.get("policy"))
    quality_policy = policy.quality_policy
    insights = dict(final_state.get("insights") or {})
    quality_metrics = dict(insights.get("quality_metrics") or {})
    failures: list[str] = []
    score = 100

    claim_coverage = int(quality_metrics.get("claim_evidence_coverage") or 0)
    if claim_coverage < quality_policy.min_claim_evidence_coverage:
        failures.append(f"claim coverage too low: {claim_coverage}")
        score -= 35

    action_plan_coverage = int(insights.get("action_plan_source_coverage") or quality_metrics.get("action_plan_source_coverage") or 0)
    if action_plan_coverage < quality_policy.min_action_plan_source_coverage:
        failures.append(f"action_plan coverage too low: {action_plan_coverage}")
        score -= 25

    return max(0, score), failures


def _score_insight(final_state: dict[str, Any]) -> tuple[int, list[str]]:
    insights = dict(final_state.get("insights") or {})
    failures: list[str] = []
    score = 100

    candidate_risks = insights.get("candidate_risks") or []
    if isinstance(candidate_risks, list) and not candidate_risks:
        failures.append("missing candidate risks")
        score -= 20

    interviewer_questions = insights.get("interviewer_questions") or []
    if isinstance(interviewer_questions, list) and not interviewer_questions:
        failures.append("missing interviewer questions")
        score -= 20

    action_plan_items = insights.get("action_plan_items") or []
    if isinstance(action_plan_items, list) and not action_plan_items:
        failures.append("missing action plan items")
        score -= 20

    if isinstance(insights.get("evidence_gap_summary") or [], list) and len(insights.get("evidence_gap_summary") or []) >= 4:
        score -= 10

    return max(0, score), failures


def _score_report_compliance(case: ResearchCase, final_state: dict[str, Any]) -> tuple[int, list[str]]:
    policy = coerce_policy(final_state.get("policy"))
    report_policy = policy.report_policy
    failures: list[str] = []
    score = 100
    report = str(final_state.get("report_content") or "")
    insights = dict(final_state.get("insights") or {})

    for section in report_policy.required_sections:
        if section not in report:
            failures.append(f"missing report section: {section}")
            score -= 10

    if report.count("http") < report_policy.min_source_urls_in_report:
        failures.append("insufficient source urls")
        score -= 20

    if case.company_assertions:
        joined = " ".join([report] + [str(item) for item in insights.get("company_specific_requirements") or []])
        for assertion in case.company_assertions:
            if assertion not in joined:
                failures.append(f"missing company assertion: {assertion}")
                score -= 15
                break

    return max(0, score), failures


def score_case_result(case: ResearchCase, final_state: dict[str, Any]) -> CaseEvaluation:
    policy = coerce_policy(final_state.get("policy"))
    eval_policy = policy.eval_policy
    failures: list[str] = []

    actual_intent = str(final_state.get("intent") or "")
    if actual_intent != case.expected_intent:
        failures.append(f"intent mismatch: expected={case.expected_intent}, actual={actual_intent}")

    retrieval_score, retrieval_failures = _score_retrieval(case, final_state)
    attribution_score, attribution_failures = _score_attribution(final_state)
    insight_score, insight_failures = _score_insight(final_state)
    report_score, report_failures = _score_report_compliance(case, final_state)
    failures.extend(retrieval_failures + attribution_failures + insight_failures + report_failures)

    quality_mode = str(final_state.get("quality_mode") or "normal")
    if not case.allow_conservative and quality_mode == "conservative":
        failures.append("unexpected conservative mode")

    node_scores = NodeScorecard(
        retrieval=retrieval_score,
        attribution=attribution_score,
        insight=insight_score,
        report_compliance=report_score,
    )

    thresholds_failed = any(
        [
            retrieval_score < eval_policy.min_retrieval_score,
            attribution_score < eval_policy.min_attribution_score,
            insight_score < eval_policy.min_insight_score,
            report_score < eval_policy.min_report_compliance_score,
        ]
    )

    average_score = round(
        (retrieval_score + attribution_score + insight_score + report_score) / 4,
    )
    return CaseEvaluation(
        case_id=case.case_id,
        passed=(not failures) and (not thresholds_failed),
        score=max(0, average_score),
        expected_intent=case.expected_intent,
        actual_intent=actual_intent,
        failures=failures,
        root_cause=str((dict(final_state.get("quality_summary") or {})).get("root_cause") or final_state.get("root_cause") or ""),
        quality_mode=quality_mode,
        metrics={
            "evidence_count": int((dict(final_state.get("insights") or {})).get("evidence_count") or 0),
            "company_specific_source_count": int((dict(final_state.get("insights") or {})).get("company_specific_source_count") or 0),
            "claim_evidence_coverage": int((dict((dict(final_state.get("insights") or {})).get("quality_metrics") or {})).get("claim_evidence_coverage") or 0),
            "action_plan_source_coverage": int((dict(final_state.get("insights") or {})).get("action_plan_source_coverage") or 0),
        },
        node_scores=node_scores,
        metadata=_build_eval_metadata(case, final_state),
    )


def summarize_eval_suite(suite_name: str, case_results: list[CaseEvaluation]) -> EvalSuiteSummary:
    passed_cases = sum(1 for item in case_results if item.passed)
    root_cause_breakdown: dict[str, int] = {}
    for result in case_results:
        key = result.root_cause or "unknown"
        root_cause_breakdown[key] = root_cause_breakdown.get(key, 0) + 1
    average_score = round(sum(item.score for item in case_results) / len(case_results), 2) if case_results else 0.0
    return EvalSuiteSummary(
        suite_name=suite_name,
        total_cases=len(case_results),
        passed_cases=passed_cases,
        failed_cases=len(case_results) - passed_cases,
        average_score=average_score,
        root_cause_breakdown=root_cause_breakdown,
        case_results=case_results,
    )
