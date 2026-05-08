"""Unified Gate — pure rule checks, 0 LLM. Merges QualityGate + VerifierAgent."""

from __future__ import annotations

from typing import Any

from api.core.constants import FORBIDDEN_PHRASES
from api.core.contracts import GateOutput, GateStatus


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


def run_gate(
    *,
    artifacts: dict[str, Any] | None = None,
    working_set: dict[str, Any] | None = None,
    background: dict[str, Any] | None = None,
    report_content: str = "",
    min_evidence_count: int = 4,
    min_company_specific: int = 2,
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
    es = _check_evidence_sufficiency(evidence_items, min_evidence_count)
    if es:
        issues.append(es)
        checked_rules.append("evidence_sufficiency")
        if status != "rejected":
            status = "downgraded"

    # 5. Company specificity
    cs = _check_company_specificity(evidence_items, min_company_specific)
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

    # Fill checked rules
    all_rules = [
        "evidence_sufficiency", "company_specificity", "candidate_fact_boundary",
        "evidence_refs", "forbidden_phrases", "fiction_detection",
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
