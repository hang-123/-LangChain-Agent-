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


def _score_matching(case: ResearchCase, final_state: dict[str, Any]) -> tuple[int, list[str]]:
    ground_truth = dict(case.match_ground_truth or {})
    if not ground_truth:
        return 100, []
    match_assessment = dict(final_state.get("match_assessment") or {})
    if not match_assessment:
        return 0, ["match_assessment missing from state"]

    failures: list[str] = []
    score = 100

    # score_alignment: overall_score vs ground truth minimum
    overall_score = int(match_assessment.get("overall_score") or 0)
    min_overall = int(ground_truth.get("min_overall_score") or 0)
    if overall_score < min_overall:
        penalty = min(40, (min_overall - overall_score) * 2)
        failures.append(f"score_alignment: overall_score {overall_score} < min {min_overall}")
        score -= penalty

    # recommendation_accuracy (P0 if mismatch)
    actual_rec = str(match_assessment.get("recommendation") or "")
    expected_rec = str(ground_truth.get("expected_recommendation") or "")
    if expected_rec and actual_rec != expected_rec:
        failures.append(f"recommendation_accuracy: expected {expected_rec}, got {actual_rec}")
        score -= 35

    # must_have_recall: strengths reflecting must-have coverage
    min_must_have_ratio = float(ground_truth.get("min_must_have_match_ratio") or 0)
    strengths = list(match_assessment.get("strengths") or [])
    gaps = list(match_assessment.get("gaps") or [])
    total_req = len(strengths) + len(gaps)
    strength_ratio = len(strengths) / total_req if total_req > 0 else 0.0
    if strength_ratio < min_must_have_ratio:
        failures.append(f"must_have_recall: strength_ratio {strength_ratio:.2f} < min {min_must_have_ratio}")
        score -= 25

    # evidence_precision: strengths/gaps with evidence_refs
    min_strengths = int(ground_truth.get("min_strengths") or 0)
    max_gaps = int(ground_truth.get("max_gaps") or 99)
    if len(strengths) < min_strengths:
        failures.append(f"evidence_precision: strengths count {len(strengths)} < min {min_strengths}")
        score -= 15
    if len(gaps) > max_gaps:
        failures.append(f"evidence_precision: gaps count {len(gaps)} > max {max_gaps}")
        score -= 15

    return max(0, score), failures


def _score_resume(case: ResearchCase, final_state: dict[str, Any]) -> tuple[int, list[str]]:
    ground_truth = dict(case.resume_ground_truth or {})
    if not ground_truth:
        return 100, []
    resume_version = dict(final_state.get("resume_version") or {})
    fact_check_report = dict(final_state.get("fact_check_report") or {})
    tailor_plan = dict(final_state.get("tailor_plan") or {})
    if not resume_version and not tailor_plan:
        return 0, ["resume_version and tailor_plan missing from state"]

    failures: list[str] = []
    score = 100

    # fact_faithfulness (P0: any fabrication → 0)
    fact_check_status = str(fact_check_report.get("status") or resume_version.get("fact_check_status") or "unknown")
    forbidden_phrases = list(ground_truth.get("forbidden_phrases") or [])
    resume_text = " ".join([
        str(resume_version.get("summary_text") or ""),
        " ".join(str(b) for b in resume_version.get("project_bullets") or []),
        " ".join(str(k) for k in resume_version.get("keyword_insertions") or []),
    ]).lower()

    fabrication_hits: list[str] = []
    for phrase in forbidden_phrases:
        if phrase.lower() in resume_text:
            fabrication_hits.append(phrase)

    if fact_check_status == "rejected" or fabrication_hits:
        failures.append(f"fact_faithfulness P0: status={fact_check_status}, fabrications={fabrication_hits}")
        return 0, failures

    if fact_check_status == "downgraded":
        failures.append(f"fact_faithfulness: status downgraded")
        score -= 25
    elif fact_check_status != "passed":
        failures.append(f"fact_faithfulness: unknown status {fact_check_status}")
        score -= 10

    # keyword_coverage
    keyword_coverage = dict(tailor_plan.get("keyword_coverage") or {})
    covered_keywords = list(keyword_coverage.get("covered") or [])
    min_keyword_covered = int(ground_truth.get("min_keyword_covered") or 0)
    if len(covered_keywords) < min_keyword_covered:
        failures.append(f"keyword_coverage: covered {len(covered_keywords)} < min {min_keyword_covered}")
        score -= 20

    require_keywords = list(ground_truth.get("require_keywords") or [])
    resume_full = " ".join([resume_text] + covered_keywords).lower()
    missing_required = [kw for kw in require_keywords if kw.lower() not in resume_full]
    if missing_required:
        failures.append(f"keyword_coverage: missing required keywords {missing_required}")
        score -= 15

    # job_relevance: has section_actions
    section_actions = list(tailor_plan.get("section_actions") or [])
    min_section_actions = int(ground_truth.get("min_section_actions") or 0)
    if len(section_actions) < min_section_actions:
        failures.append(f"job_relevance: section_actions {len(section_actions)} < min {min_section_actions}")
        score -= 15

    return max(0, score), failures


def _score_interview(case: dict, state: dict) -> int:
    """Score interview prep quality per spec 32.

    Dimensions:
    - question_relevance: questions match expected role keywords
    - question_diversity: covers behavioral / technical / project_deep_dive
    - evidence_grounding: questions bound to evidence_refs
    - actionability: practice advice present

    Returns score 0-100.
    """
    gt = dict(case.get("interview_ground_truth") or {})
    prep_pack = dict(state.get("prep_pack") or {})

    if not prep_pack:
        return 0

    behavioral = list(prep_pack.get("behavioral_questions") or [])
    technical = list(prep_pack.get("technical_questions") or [])
    deep_dive = list(prep_pack.get("project_deep_dive") or [])
    risk_qs = list(prep_pack.get("risk_questions") or [])
    advice = list(prep_pack.get("practice_advice") or [])

    penalties = 0

    # ── question_relevance (max -25) ──
    expected_keywords = gt.get("expected_role_keywords", [])
    if expected_keywords:
        all_qs = behavioral + technical + deep_dive + risk_qs
        all_text = " ".join(
            q.get("question", "") + " " + q.get("answer_framework", "")
            for q in all_qs
        ).lower()
        keyword_hits = sum(1 for kw in expected_keywords if kw.lower() in all_text)
        if keyword_hits < len(expected_keywords):
            penalties += int(25 * (1 - keyword_hits / len(expected_keywords)))

    # ── question_diversity (max -30) ──
    min_behavioral = gt.get("min_behavioral_questions", 2)
    min_technical = gt.get("min_technical_questions", 1)
    min_deep_dive = gt.get("min_project_deep_dive", 1)

    if len(behavioral) < min_behavioral:
        penalties += 10 * (min_behavioral - len(behavioral))
    if len(technical) < min_technical:
        penalties += 10 * (min_technical - len(technical))
    if len(deep_dive) < min_deep_dive:
        penalties += 10 * (min_deep_dive - len(deep_dive))

    # ── evidence_grounding (max -25) ──
    all_with_refs = [q for q in behavioral + technical + deep_dive
                     if q.get("evidence_refs") and len(q.get("evidence_refs", [])) > 0]
    total_qs = len(behavioral) + len(technical) + len(deep_dive)
    if total_qs > 0:
        grounding_ratio = len(all_with_refs) / total_qs
        if grounding_ratio < 0.5:
            penalties += int(25 * (1 - grounding_ratio))

    # ── actionability (max -10) ──
    if len(advice) < 2:
        penalties += 5 * (2 - len(advice))

    # ── risk questions (max -10) ──
    required_risk = gt.get("required_risk_questions", 0)
    if len(risk_qs) < required_risk:
        penalties += 10 * (required_risk - len(risk_qs))

    return max(0, 100 - penalties)


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
    matching_score, matching_failures = _score_matching(case, final_state)
    resume_score, resume_failures = _score_resume(case, final_state)
    interview_score = _score_interview(case.model_dump(), final_state)
    routing_score = 100  # routing scorer not yet implemented; default pass
    failures.extend(retrieval_failures + attribution_failures + insight_failures + report_failures + matching_failures + resume_failures)

    quality_mode = str(final_state.get("quality_mode") or "normal")
    if not case.allow_conservative and quality_mode == "conservative":
        failures.append("unexpected conservative mode")

    node_scores = NodeScorecard(
        retrieval=retrieval_score,
        attribution=attribution_score,
        insight=insight_score,
        report_compliance=report_score,
        matching=matching_score,
        resume=resume_score,
        interview=interview_score,
        routing=routing_score,
    )

    thresholds_failed = any(
        [
            retrieval_score < eval_policy.min_retrieval_score,
            attribution_score < eval_policy.min_attribution_score,
            insight_score < eval_policy.min_insight_score,
            report_score < eval_policy.min_report_compliance_score,
            matching_score < eval_policy.min_matching_score,
            resume_score < eval_policy.min_resume_score,
        ]
    )

    # Only include relevant dimensions in the average
    case_dict = case.model_dump()
    has_interview = bool(case_dict.get("interview_ground_truth")) or bool(
        final_state.get("prep_pack", {}).get("behavioral_questions")
    )
    has_routing = bool(case_dict.get("routing_ground_truth"))

    scores_for_avg = [
        retrieval_score, attribution_score, insight_score,
        report_score, matching_score, resume_score,
    ]
    if has_interview:
        scores_for_avg.append(interview_score)
    if has_routing:
        scores_for_avg.append(routing_score)
    average_score = round(sum(scores_for_avg) / len(scores_for_avg))
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
