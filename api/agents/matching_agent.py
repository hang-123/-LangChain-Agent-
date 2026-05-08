# DEPRECATED (Phase 2): moved to api/tools/matching_engine.py.
# Retained for backward compatibility. Do not add new features here.
from __future__ import annotations

from typing import Any

from api.core.context_utils import unique_strings
from api.core.contracts import MatchAssessment
from api.core.harness import utc_now_iso


def _normalize_token(text: str) -> str:
    return " ".join(str(text or "").lower().split()).strip()


def _candidate_skill_set(candidate_profile: dict[str, Any], resume_evidence: list[dict[str, Any]]) -> set[str]:
    skills: set[str] = set()
    for skill in candidate_profile.get("skills") or []:
        clean = _normalize_token(str(skill))
        if clean:
            skills.add(clean)
    for item in resume_evidence:
        for skill in item.get("normalized_skills") or []:
            clean = _normalize_token(str(skill))
            if clean:
                skills.add(clean)
    return skills


def _resume_evidence_text(resume_evidence: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in resume_evidence:
        parts.append(str(item.get("text") or ""))
        parts.extend(str(skill) for skill in item.get("normalized_skills") or [])
    return " ".join(parts).lower()


def _match_requirement(
    requirement: dict[str, Any],
    *,
    candidate_skills: set[str],
    evidence_text: str,
    resume_evidence: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    target = _normalize_token(str(requirement.get("name") or requirement.get("description") or ""))
    if not target:
        return False, []
    matched_refs: list[str] = []
    if target in candidate_skills or target in evidence_text:
        for item in resume_evidence:
            item_text = _normalize_token(str(item.get("text") or ""))
            skill_hits = {_normalize_token(str(skill)) for skill in item.get("normalized_skills") or []}
            if target in item_text or target in skill_hits:
                evidence_id = str(item.get("evidence_id") or "")
                if evidence_id:
                    matched_refs.append(evidence_id)
        return True, unique_strings(matched_refs)
    return False, []


def _recommendation(overall_score: int) -> str:
    if overall_score >= 82:
        return "strong_recommend"
    if overall_score >= 68:
        return "recommended_with_risks"
    if overall_score >= 50:
        return "neutral"
    return "not_recommended"


async def matching_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    candidate_profile = dict(state.get("candidate_profile") or {})
    resume_evidence = list(state.get("resume_evidence") or [])
    job_snapshot = dict(state.get("job_snapshot") or {})
    job_requirements = list(job_snapshot.get("job_requirements") or [])
    if not job_snapshot or not job_requirements:
        return {
            "match_assessment": {},
            "status": "🧭 MatchingAgent 未生成正式匹配分：缺少 JobSnapshot 或岗位要求结构化结果。",
        }

    candidate_id = str(candidate_profile.get("candidate_id") or "candidate::unknown")
    job_id = str(job_snapshot.get("job_id") or "job::unknown")
    candidate_skills = _candidate_skill_set(candidate_profile, resume_evidence)
    evidence_text = _resume_evidence_text(resume_evidence)
    must_have_reqs = [req for req in job_requirements if str(req.get("requirement_level") or "") == "must_have"]
    other_reqs = [req for req in job_requirements if req not in must_have_reqs]
    strengths: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    matched_must_have = 0
    matched_other = 0

    for requirement in must_have_reqs + other_reqs:
        matched, matched_refs = _match_requirement(
            requirement,
            candidate_skills=candidate_skills,
            evidence_text=evidence_text,
            resume_evidence=resume_evidence,
        )
        requirement_id = str(requirement.get("requirement_id") or "")
        req_name = str(requirement.get("name") or requirement.get("description") or "未命名要求")
        if matched:
            if requirement in must_have_reqs:
                matched_must_have += 1
            else:
                matched_other += 1
            strengths.append(
                {
                    "title": f"已覆盖 {req_name} 要求",
                    "evidence_refs": unique_strings(matched_refs + ([requirement_id] if requirement_id else [])),
                }
            )
        else:
            gaps.append(
                {
                    "title": f"缺少 {req_name} 证据",
                    "severity": "high" if requirement in must_have_reqs else "medium",
                    "evidence_refs": [requirement_id] if requirement_id else [],
                }
            )

    skill_ratio = matched_must_have / len(must_have_reqs) if must_have_reqs else 0.0
    secondary_ratio = matched_other / len(other_reqs) if other_reqs else 0.5
    experience_score = 72 if float(candidate_profile.get("years_of_experience") or 0) >= 1 else 58
    education_score = 85 if candidate_profile.get("education") else 55
    job_posting = dict(job_snapshot.get("job_posting") or {})
    job_title = _normalize_token(str(job_posting.get("job_title") or ""))
    target_roles = [_normalize_token(str(item)) for item in candidate_profile.get("target_roles") or []]
    domain_fit = 78 if job_title and any(job_title in role or role in job_title for role in target_roles) else 60
    city = _normalize_token(str(job_posting.get("city") or ""))
    location_preferences = {_normalize_token(str(item)) for item in candidate_profile.get("location_preferences") or []}
    location_score = 90 if city and city in location_preferences else 65 if not city else 55
    skills_score = round(skill_ratio * 80 + secondary_ratio * 20)
    overall_score = round(
        skills_score * 0.45
        + experience_score * 0.2
        + domain_fit * 0.15
        + education_score * 0.1
        + location_score * 0.1
    )
    if must_have_reqs and matched_must_have < len(must_have_reqs):
        overall_score = min(overall_score, 76)
    if not resume_evidence:
        overall_score = min(overall_score, 58)
        risks.append({"title": "缺少 ResumeEvidence，当前匹配分析已按保守模式降级。", "severity": "high"})
    ambiguity_notes = list((job_snapshot.get("evidence_quality") or {}).get("ambiguity_notes") or [])
    for note in ambiguity_notes[:2]:
        risks.append({"title": str(note), "severity": "medium"})

    dimension_scores = {
        "skills": max(0, min(100, skills_score)),
        "experience": experience_score,
        "domain_fit": domain_fit,
        "education": education_score,
        "location_fit": location_score,
    }
    reasoning_notes = ["匹配结论仅基于简历显式证据和岗位快照，不推测未写明经历。"]
    if not resume_evidence:
        reasoning_notes.append("由于缺少 ResumeEvidence，本轮评分采取保守降级。")

    assessment = MatchAssessment(
        assessment_id=f"match::{candidate_id}::{job_id}",
        candidate_id=candidate_id,
        job_id=job_id,
        overall_score=max(0, min(100, overall_score)),
        recommendation=_recommendation(overall_score),
        strengths=strengths[:4],
        gaps=gaps[:4],
        risks=risks[:4],
        dimension_scores=dimension_scores,
        reasoning_notes=reasoning_notes,
        created_at=utc_now_iso(),
    )
    return {
        "match_assessment": assessment.model_dump(mode="json"),
        "status": f"🎯 MatchingAgent 已完成匹配分析，当前建议：{assessment.recommendation}，综合分 {assessment.overall_score}。",
    }
