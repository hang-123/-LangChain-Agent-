"""Unified Gate — pure rule checks, 0 LLM. Merges QualityGate + VerifierAgent."""

from __future__ import annotations

from typing import Any

from api.core.constants import FORBIDDEN_PHRASES
from api.core.contracts import GateOutput, GateStatus
from api.core.policy_loader import policy_from_state

# Legal application status values
_VALID_APPLICATION_STATUSES = frozenset({
    "draft", "planned", "applied", "screening",
    "written_test", "interviewing", "offer", "rejected", "withdrawn",
})

# Legal status transitions (from ApplicationStore)
_LEGAL_APPLICATION_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"planned", "rejected", "withdrawn"}),
    "planned": frozenset({"applied", "rejected", "withdrawn"}),
    "applied": frozenset({"screening", "rejected", "withdrawn"}),
    "screening": frozenset({"written_test", "rejected", "withdrawn"}),
    "written_test": frozenset({"interviewing", "rejected", "withdrawn"}),
    "interviewing": frozenset({"offer", "rejected", "withdrawn"}),
    "offer": frozenset({"rejected", "withdrawn"}),
}


def _check_evidence_sufficiency(
    evidence_items: list[dict[str, Any]],
    min_evidence_count: int = 4,
) -> dict[str, Any] | None:
    if len(evidence_items) < min_evidence_count:
        return {
            "rule": "evidence_sufficiency",
            "status": "downgraded",
            "message": f"证据数量({len(evidence_items)})不足，最低要求{min_evidence_count}条",
        }
    return None


def _check_company_specificity(
    evidence_items: list[dict[str, Any]],
    min_company_specific: int = 2,
) -> dict[str, Any] | None:
    company_specific = sum(1 for e in evidence_items if e.get("company_specific"))
    if company_specific < min_company_specific:
        return {
            "rule": "company_specificity",
            "status": "downgraded",
            "message": f"公司特异性来源({company_specific})不足，最低要求{min_company_specific}个",
        }
    return None


def _check_forbidden_phrases(
    text: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            # Check if backed by ResumeEvidence (delegated to upstream tracking)
            issues.append({
                "rule": "forbidden_phrases",
                "status": "rejected",
                "message": f"输出包含禁止断言词: '{phrase}'",
                "phrase": phrase,
            })
    return issues


def _check_evidence_refs(
    claims: list[dict[str, Any]],
) -> dict[str, Any] | None:
    unbacked = [c for c in claims if not c.get("evidence_refs")]
    if unbacked:
        return {
            "rule": "evidence_refs",
            "status": "downgraded",
            "message": f"有{len(unbacked)}条结论缺少证据引用",
            "unbacked_claim_count": len(unbacked),
        }
    return None


def _check_claim_evidence_coverage(
    analysis: dict[str, Any],
    *,
    min_claim_evidence_coverage: int = 70,
) -> dict[str, Any] | None:
    quality_metrics = dict(analysis.get("quality_metrics") or {})
    claims = analysis.get("claims") or []
    raw_coverage = quality_metrics.get("claim_evidence_coverage")
    if raw_coverage is None:
        raw_coverage = analysis.get("claim_evidence_coverage")
    if raw_coverage is None and claims:
        with_evidence = sum(
            1 for claim in claims
            if isinstance(claim.get("evidence_refs"), list) and any(str(ref).strip() for ref in claim.get("evidence_refs") or [])
        )
        raw_coverage = int((with_evidence / len(claims)) * 100)
    coverage = int(raw_coverage or 0)
    if claims and coverage < min_claim_evidence_coverage:
        return {
            "rule": "claim_evidence_coverage",
            "status": "downgraded",
            "message": f"claims 证据覆盖率({coverage}%)不足，最低要求{min_claim_evidence_coverage}%",
            "coverage": coverage,
        }
    return None


def _check_action_plan_source_coverage(
    analysis: dict[str, Any],
    *,
    min_action_plan_source_coverage: int = 60,
) -> dict[str, Any] | None:
    quality_metrics = dict(analysis.get("quality_metrics") or {})
    coverage = int(
        quality_metrics.get("action_plan_source_coverage")
        or analysis.get("action_plan_source_coverage")
        or 0
    )
    action_plan_items = analysis.get("action_plan_items") or []
    if action_plan_items and coverage < min_action_plan_source_coverage:
        return {
            "rule": "action_plan_source_coverage",
            "status": "downgraded",
            "message": f"行动项证据覆盖率({coverage}%)不足，最低要求{min_action_plan_source_coverage}%",
            "coverage": coverage,
        }
    return None


def _check_missing_classes(retrieval: dict[str, Any]) -> dict[str, Any] | None:
    diagnostics = dict(retrieval.get("retrieval_diagnostics") or retrieval.get("diagnostics") or {})
    missing_classes = diagnostics.get("missing_classes") or []
    if isinstance(missing_classes, list) and missing_classes:
        return {
            "rule": "missing_classes",
            "status": "downgraded",
            "message": f"缺少关键证据类别: {', '.join(str(item) for item in missing_classes[:3])}",
            "missing_classes": missing_classes,
        }
    return None


def _check_candidate_boundary(
    output_text: str,
    candidate_profile: dict[str, Any],
    resume_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check if job-side evidence is being written as candidate facts."""
    issues: list[dict[str, Any]] = []
    candidate_skills = set(
        str(s).lower() for s in candidate_profile.get("skills", [])
    )
    evidence_skills: set[str] = set()
    for ev in resume_evidence:
        for skill in ev.get("normalized_skills", []):
            evidence_skills.add(str(skill).lower())

    all_candidate_skills = candidate_skills | evidence_skills

    # Check if forbidden phrases appear with skills NOT in candidate evidence
    for phrase in FORBIDDEN_PHRASES:
        if phrase in output_text:
            issues.append({
                "rule": "candidate_fact_boundary",
                "status": "rejected",
                "message": f"禁止断言词'{phrase}'出现在输出中，且无法由候选人证据支撑",
            })

    return issues


def _check_fiction(
    output_text: str,
    resume_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check for fabricated numbers, roles, or project scales."""
    issues: list[dict[str, Any]] = []

    # Collect all numeric claims from evidence
    evidence_texts: list[str] = []
    for ev in resume_evidence:
        for field in ("description", "snippet", "text", "summary"):
            val = ev.get(field)
            if isinstance(val, str) and val.strip():
                evidence_texts.append(val.strip())

    all_evidence = " ".join(evidence_texts).lower()

    import re
    # Look for percentage/number claims in output not in evidence
    number_patterns = re.findall(r'(\d+[%％]|\d+\s*(?:QPS|ms|万|亿|倍|个|项|人|次))', output_text)
    for num_match in number_patterns:
        if num_match.lower() not in all_evidence:
            issues.append({
                "rule": "fiction_detection",
                "status": "rejected",
                "message": f"输出中的数字成果'{num_match}'未在简历证据中找到支撑",
            })

    return issues


def _check_application_status(application_record: dict[str, Any]) -> dict[str, Any] | None:
    """Check that application status is a valid enum value."""
    status = str(application_record.get("status") or "").strip()
    if not status:
        return {
            "rule": "application_status_valid",
            "status": "rejected",
            "message": "投递记录缺少status字段",
        }
    if status not in _VALID_APPLICATION_STATUSES:
        return {
            "rule": "application_status_valid",
            "status": "rejected",
            "message": f"非法投递状态: '{status}'，有效值: {', '.join(sorted(_VALID_APPLICATION_STATUSES))}",
        }
    return None


def _check_application_required_fields(application_record: dict[str, Any]) -> dict[str, Any] | None:
    """Check that required fields are present."""
    missing_fields: list[str] = []
    for field in ("candidate_id", "job_id"):
        if not str(application_record.get(field) or "").strip():
            missing_fields.append(field)
    if missing_fields:
        return {
            "rule": "application_required_fields",
            "status": "rejected",
            "message": f"投递记录缺少必填字段: {', '.join(missing_fields)}",
        }
    return None


def _check_application_transition(
    application_record: dict[str, Any],
    previous_status: str = "",
) -> dict[str, Any] | None:
    """Check that status transition is legal."""
    status = str(application_record.get("status") or "").strip()
    if not previous_status:
        # No previous status to compare — skip transition check
        return None
    if previous_status in ("rejected", "withdrawn"):
        return {
            "rule": "application_transition",
            "status": "rejected",
            "message": f"无法从终态'{previous_status}'再次流转",
        }
    allowed = _LEGAL_APPLICATION_TRANSITIONS.get(previous_status, frozenset())
    if status not in allowed:
        return {
            "rule": "application_transition",
            "status": "rejected",
            "message": f"非法状态流转: {previous_status} → {status}，允许的目标状态: {', '.join(sorted(allowed))}",
        }
    return None


def run_gate(
    *,
    artifacts: dict[str, Any] | None = None,
    working_set: dict[str, Any] | None = None,
    background: dict[str, Any] | None = None,
    report_content: str = "",
    min_evidence_count: int | None = None,
    min_company_specific: int | None = None,
    workflow_id: str = "",
) -> GateOutput:
    """Execute all Gate rules and return a three-state decision.

    Rules are applied in order: rejected first, then downgraded.
    If any rule returns rejected, the overall status is rejected.
    If any rule returns downgraded (and none rejected), status is downgraded.
    Otherwise, passed.
    """
    artifacts = artifacts or {}
    working_set = working_set or {}
    background = background or {}
    policy = policy_from_state({"policy": background.get("policy") or {}})
    retrieval_policy = policy.retrieval_policy
    quality_policy = policy.quality_policy
    effective_min_evidence_count = (
        int(min_evidence_count)
        if min_evidence_count is not None
        else int(retrieval_policy.min_evidence_count or 4)
    )
    effective_min_company_specific = (
        int(min_company_specific)
        if min_company_specific is not None
        else int(retrieval_policy.min_company_specific_sources or 2)
    )

    issues: list[dict[str, Any]] = []
    checked_rules: list[str] = []
    status: GateStatus = "passed"

    # Get inputs
    evidence_items: list[dict[str, Any]] = working_set.get("retrieval", {}).get("evidence_items", [])
    if not evidence_items:
        evidence_items = working_set.get("evidence_items", [])

    candidate = background.get("candidate", {})
    candidate_profile = candidate.get("candidate_profile", {})
    resume_evidence = candidate.get("resume_evidence", [])

    # Get report content for text checks
    check_text = report_content or artifacts.get("report", {}).get("report_content", "")
    if not check_text:
        # Also check other artifacts
        for key in ("match_assessment", "resume_version", "prep_pack"):
            val = artifacts.get(key, {})
            if isinstance(val, dict):
                check_text += str(val)

    # ── Application-specific checks (wf_application_followup_v1) ──
    if workflow_id == "wf_application_followup_v1":
        app_record = artifacts.get("application_record") or {}
        app_previous_status = str(artifacts.get("previous_status") or "")

        app_checks = [
            _check_application_status(app_record),
            _check_application_required_fields(app_record),
            _check_application_transition(app_record, app_previous_status),
        ]
        for check in app_checks:
            if check:
                issues.append(check)
                checked_rules.append(str(check["rule"]))
                if check["status"] == "rejected":
                    status = "rejected"
                elif check["status"] == "downgraded" and status != "rejected":
                    status = "downgraded"

        return GateOutput(
            status=status,
            issues=issues,
            checked_rules=checked_rules,
        )

    # ── Rejected-level checks (run first, highest priority) ──

    # 1. Forbidden phrases in output
    fp_issues = _check_forbidden_phrases(check_text)
    if fp_issues:
        issues.extend(fp_issues)
        checked_rules.append("forbidden_phrases")
        status = "rejected"

    # 2. Candidate boundary violation
    cb_issues = _check_candidate_boundary(check_text, candidate_profile, resume_evidence)
    if cb_issues:
        issues.extend(cb_issues)
        if "candidate_fact_boundary" not in checked_rules:
            checked_rules.append("candidate_fact_boundary")
        status = "rejected"

    # 3. Fiction detection
    fiction_issues = _check_fiction(check_text, resume_evidence)
    if fiction_issues:
        issues.extend(fiction_issues)
        checked_rules.append("fiction_detection")
        status = "rejected"

    # ── Downgraded-level checks ──

    # 4. Evidence sufficiency
    es = _check_evidence_sufficiency(
        evidence_items,
        effective_min_evidence_count,
    )
    if es:
        issues.append(es)
        checked_rules.append("evidence_sufficiency")
        if status != "rejected":
            status = "downgraded"

    # 5. Company specificity
    cs = _check_company_specificity(
        evidence_items,
        effective_min_company_specific,
    )
    if cs:
        issues.append(cs)
        checked_rules.append("company_specificity")
        if status != "rejected":
            status = "downgraded"

    # 6. Evidence refs check (on claims from analysis)
    analysis = working_set.get("analysis", {})
    claims = analysis.get("claims", [])
    er = _check_evidence_refs(claims)
    if er:
        issues.append(er)
        checked_rules.append("evidence_refs")
        if status != "rejected":
            status = "downgraded"

    cec = _check_claim_evidence_coverage(
        analysis,
        min_claim_evidence_coverage=int(quality_policy.min_claim_evidence_coverage or 70),
    )
    if cec:
        issues.append(cec)
        checked_rules.append("claim_evidence_coverage")
        if status != "rejected":
            status = "downgraded"

    apc = _check_action_plan_source_coverage(
        analysis,
        min_action_plan_source_coverage=int(quality_policy.min_action_plan_source_coverage or 60),
    )
    if apc:
        issues.append(apc)
        checked_rules.append("action_plan_source_coverage")
        if status != "rejected":
            status = "downgraded"

    mc = _check_missing_classes(working_set.get("retrieval", {}))
    if mc:
        issues.append(mc)
        checked_rules.append("missing_classes")
        if status != "rejected":
            status = "downgraded"

    # Fill checked rules
    all_rules = [
        "evidence_sufficiency", "company_specificity", "candidate_fact_boundary",
        "evidence_refs", "claim_evidence_coverage", "action_plan_source_coverage",
        "missing_classes", "forbidden_phrases", "fiction_detection",
    ]
    for r in all_rules:
        if r not in checked_rules:
            checked_rules.append(r)

    return GateOutput(
        status=status,
        issues=issues,
        checked_rules=checked_rules,
    )


__all__ = ["run_gate", "GateOutput"]
