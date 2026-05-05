from __future__ import annotations

from typing import Any

from api.core.policy_loader import policy_from_state


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _claim_metrics(claims: list[dict[str, Any]]) -> dict[str, int]:
    claim_count = len(claims)
    with_evidence = sum(
        1 for claim in claims if isinstance(claim.get("evidence_refs"), list) and any(str(ref).strip() for ref in claim.get("evidence_refs") or [])
    )
    company_specific_claims = sum(1 for claim in claims if bool(claim.get("company_specific")))
    technical_claims = sum(1 for claim in claims if str(claim.get("claim_type") or "") == "technical_stack")
    claim_evidence_coverage = int((with_evidence / claim_count) * 100) if claim_count else 0
    return {
        "claim_count": claim_count,
        "claim_with_evidence_count": with_evidence,
        "company_specific_claim_count": company_specific_claims,
        "technical_claim_count": technical_claims,
        "claim_evidence_coverage": claim_evidence_coverage,
    }


def quality_gate_node(state: dict[str, Any]) -> dict[str, Any]:
    policy = policy_from_state(state)
    retrieval_policy = policy.retrieval_policy
    quality_policy = policy.quality_policy
    insights = dict(state.get("insights") or {})
    retrieval_diagnostics = dict(state.get("retrieval_diagnostics") or {})
    claims = [claim for claim in insights.get("claims") or [] if isinstance(claim, dict)]

    evidence_count = _safe_int(insights.get("evidence_count"))
    company_specific_source_count = _safe_int(insights.get("company_specific_source_count"))
    action_plan_source_coverage = _safe_int(insights.get("action_plan_source_coverage"))
    claim_metrics = _claim_metrics(claims)
    claim_evidence_coverage = claim_metrics["claim_evidence_coverage"]

    warnings: list[str] = []
    root_cause = "synthesis"

    if evidence_count < retrieval_policy.min_evidence_count:
        warnings.append("本轮证据总量偏少，报告需要保守表达。")
    if company_specific_source_count < retrieval_policy.min_company_specific_sources:
        warnings.append("公司特异性证据不足，不能把当前结论当成强定制版建议。")
        root_cause = "retrieval"
    if claim_metrics["claim_count"] < quality_policy.min_claim_count or claim_evidence_coverage < quality_policy.min_claim_evidence_coverage:
        warnings.append("claims 证据绑定不足，说明结论归因仍然不够扎实。")
        if root_cause != "retrieval":
            root_cause = "attribution"
    if action_plan_source_coverage and action_plan_source_coverage < quality_policy.min_action_plan_source_coverage:
        warnings.append("行动项的证据覆盖率偏低，行动建议应保守降级。")
        if root_cause not in {"retrieval", "attribution"}:
            root_cause = "synthesis"

    missing_classes = retrieval_diagnostics.get("missing_classes") or []
    if isinstance(missing_classes, list) and missing_classes:
        warnings.append(f"缺少关键证据类别：{', '.join(str(item) for item in missing_classes[:3])}。")
        root_cause = "retrieval"

    quality_mode = "conservative" if warnings else "normal"
    warning_message = " ".join(warnings[:3]).strip()

    quality_metrics = dict(insights.get("quality_metrics") or {})
    quality_metrics.update(
        {
            "claim_count": claim_metrics["claim_count"],
            "claim_with_evidence_count": claim_metrics["claim_with_evidence_count"],
            "claim_evidence_coverage": claim_evidence_coverage,
            "company_specific_claim_count": claim_metrics["company_specific_claim_count"],
            "technical_claim_count": claim_metrics["technical_claim_count"],
            "action_plan_source_coverage": action_plan_source_coverage,
            "evidence_count": evidence_count,
            "company_specific_source_count": company_specific_source_count,
        }
    )

    insights["quality_metrics"] = quality_metrics
    insights["root_cause_hint"] = root_cause

    return {
        "insights": insights,
        "quality_mode": quality_mode,
        "warning_message": warning_message,
        "root_cause": root_cause,
        "status": (
            "🛡️ 质量闸门通过，当前可以按正常模式成稿。"
            if quality_mode == "normal"
            else f"🛡️ 质量闸门判定为保守降级模式：{warning_message}"
        ),
    }
