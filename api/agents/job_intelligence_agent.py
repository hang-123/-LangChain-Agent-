# DEPRECATED (Phase 2): absorbed into api/tools/job_analyzer.py.
# Retained for backward compatibility. Do not add new features here.
from __future__ import annotations

from typing import Any

from api.core.context_utils import coerce_evidence_items, unique_strings
from api.core.contracts import ExternalEvidenceItem, ExternalEvidencePack, JobSnapshot


SUPPORTED_SOURCE_CLASSES = {"company_profile", "jd", "interview", "tech_stack", "salary_culture"}


def _job_id(profile: dict[str, Any], insights: dict[str, Any]) -> str:
    company = str(insights.get("company") or profile.get("company") or "target-company").strip() or "target-company"
    role = str(insights.get("role") or profile.get("role") or "target-role").strip() or "target-role"
    return f"job::{company}::{role}"


def _to_external_source(item: dict[str, Any]) -> ExternalEvidenceItem:
    quality_score = int(item.get("quality_score") or 0)
    return ExternalEvidenceItem(
        source_id=str(item.get("source_id") or ""),
        source_type=str(item.get("source_class") or "unknown"),
        title=str(item.get("title") or "无标题"),
        url=str(item.get("url") or ""),
        snippet=str(item.get("snippet") or ""),
        freshness_score=int(item.get("freshness_score") or 0),
        confidence=round(max(0.0, min(1.0, quality_score / 100)), 2),
        evidence_class=str(item.get("source_class") or "unknown"),
    )


def build_external_evidence_pack(
    *,
    job_id: str,
    evidence_items: list[dict[str, Any]],
    insights: dict[str, Any],
) -> ExternalEvidencePack:
    filtered_items = [
        item for item in coerce_evidence_items(evidence_items) if str(item.get("source_class") or "") in SUPPORTED_SOURCE_CLASSES
    ]
    company_signals = unique_strings(
        [str(item) for item in insights.get("company_signals") or []]
        + [str(item) for item in insights.get("business_domain_hints") or []]
    )[:4]
    interview_signals = unique_strings([str(item) for item in insights.get("interview_expectations") or []])[:4]
    risk_flags = unique_strings(
        [str(item) for item in insights.get("coverage_gaps") or []]
        + [str(item) for item in insights.get("search_failures") or []]
    )[:6]
    return ExternalEvidencePack(
        evidence_pack_id=f"jep::{job_id}",
        job_id=job_id,
        sources=[_to_external_source(item) for item in filtered_items],
        company_signals=company_signals,
        interview_signals=interview_signals,
        risk_flags=risk_flags,
    )


def _build_job_posting(
    *,
    job_id: str,
    profile: dict[str, Any],
    insights: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    raw_jd_text: str,
) -> dict[str, Any]:
    jd_source = next((item for item in evidence_items if str(item.get("source_class") or "") == "jd"), {})
    return {
        "job_id": job_id,
        "company_name": str(insights.get("company") or profile.get("company") or ""),
        "job_title": str(insights.get("role") or profile.get("role") or ""),
        "source_type": "research_enhanced",
        "source_url": str(jd_source.get("url") or ""),
        "raw_jd_text": raw_jd_text,
        "business_domain": (
            str((insights.get("business_domain_hints") or [profile.get("domain_hint") or ""])[0] or "")
        ),
        "normalized_requirements": unique_strings(
            [str(item) for item in insights.get("company_specific_requirements") or []]
            + [str(item) for item in insights.get("technical_stack_requirements") or []]
        )[:6],
    }


def _requirement_item(job_id: str, index: int, statement: str, requirement_level: str, category: str) -> dict[str, Any]:
    return {
        "requirement_id": f"{job_id}::req::{index}",
        "job_id": job_id,
        "category": category,
        "name": statement,
        "requirement_level": requirement_level,
        "importance_weight": 0.9 if requirement_level == "must_have" else 0.6,
        "description": statement,
        "evidence_text": statement,
        "confidence": 0.8 if requirement_level == "must_have" else 0.65,
    }


def _build_job_requirements(job_id: str, insights: dict[str, Any]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    index = 1
    for statement in insights.get("company_specific_requirements") or []:
        requirements.append(_requirement_item(job_id, index, str(statement), "must_have", "domain"))
        index += 1
    for statement in insights.get("technical_stack_requirements") or []:
        requirements.append(_requirement_item(job_id, index, str(statement), "must_have", "skill"))
        index += 1
    for statement in insights.get("common_requirements") or []:
        requirements.append(_requirement_item(job_id, index, str(statement), "nice_to_have", "general"))
        index += 1
    return requirements


def build_job_snapshot(
    *,
    job_id: str,
    job_posting: dict[str, Any],
    job_requirements: list[dict[str, Any]],
    evidence_pack: ExternalEvidencePack,
    insights: dict[str, Any],
) -> JobSnapshot:
    freshness_values = [source.freshness_score for source in evidence_pack.sources]
    freshness = round(sum(freshness_values) / len(freshness_values)) if freshness_values else 0
    context_quality_score = int(insights.get("context_quality_score") or 0)
    return JobSnapshot(
        job_snapshot_id=f"js::{job_id}",
        job_id=job_id,
        job_posting=job_posting,
        job_requirements=job_requirements,
        external_evidence_pack_id=evidence_pack.evidence_pack_id,
        evidence_quality={
            "freshness": freshness,
            "coverage": round(context_quality_score / 100, 2),
            "ambiguity_notes": unique_strings(
                [str(item) for item in insights.get("coverage_gaps") or []] + list(evidence_pack.risk_flags)
            )[:6],
        },
    )


async def job_intelligence_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    profile = dict(state.get("query_profile") or {})
    insights = dict(state.get("insights") or {})
    evidence_items = coerce_evidence_items(state.get("evidence_items"), list(state.get("context") or []))
    job_id = _job_id(profile, insights)
    evidence_pack = build_external_evidence_pack(job_id=job_id, evidence_items=evidence_items, insights=insights)
    job_posting = _build_job_posting(
        job_id=job_id,
        profile=profile,
        insights=insights,
        evidence_items=evidence_items,
        raw_jd_text=str(state.get("raw_jd_text") or ""),
    )
    job_requirements = _build_job_requirements(job_id, insights)
    job_snapshot = build_job_snapshot(
        job_id=job_id,
        job_posting=job_posting,
        job_requirements=job_requirements,
        evidence_pack=evidence_pack,
        insights=insights,
    )
    return {
        "external_evidence_pack": evidence_pack.model_dump(mode="json"),
        "job_snapshot": job_snapshot.model_dump(mode="json"),
        "status": f"🧩 已基于 research artifacts 生成 JobSnapshot，包含 {len(job_requirements)} 条岗位要求与 {len(evidence_pack.sources)} 条外部证据。",
    }
