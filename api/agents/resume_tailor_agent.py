from __future__ import annotations

from typing import Any

from api.core.context_utils import clip_text, unique_strings
from api.core.contracts import FactCheckReport, ResumeTailorSectionAction, ResumeTailoringPlan, ResumeVersion
from api.core.harness import utc_now_iso


TAILOR_KEYWORDS = [
    "Java",
    "Go",
    "Python",
    "C++",
    "Redis",
    "MySQL",
    "Kafka",
    "Spring",
    "Spring Boot",
    "HTTP",
    "RPC",
    "微服务",
    "分布式",
    "高并发",
    "系统设计",
]


SECTION_ALIASES = {
    "project": "projects",
    "projects": "projects",
    "work experience": "work_experience",
    "work experiences": "work_experience",
    "work_experience": "work_experience",
    "skill": "skills",
    "skills": "skills",
    "certificate": "certificates",
    "certificates": "certificates",
    "education": "education",
    "user input": "user_input",
    "user_input": "user_input",
}


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _normalize_section_name(value: Any) -> str:
    normalized = " ".join(str(value or "").replace("-", " ").replace("_", " ").split()).lower()
    if not normalized:
        return ""
    return SECTION_ALIASES.get(normalized, normalized.replace(" ", "_"))


def _keyword_matches(text: str, keyword: str) -> bool:
    haystack = str(text or "")
    needle = str(keyword or "").strip()
    if not haystack or not needle:
        return False
    if any(char.isalnum() for char in needle):
        import re

        pattern = r"(?<![A-Za-z0-9+])" + re.escape(needle) + r"(?![A-Za-z0-9+])"
        return re.search(pattern, haystack, flags=re.IGNORECASE) is not None
    return needle in haystack


def _requirement_keywords(requirement: dict[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(requirement.get("name") or ""),
            str(requirement.get("description") or ""),
            str(requirement.get("evidence_text") or ""),
        ]
    )
    hits = [keyword for keyword in TAILOR_KEYWORDS if _keyword_matches(text, keyword)]
    if hits:
        return unique_strings(hits)[:4]
    fallback = clip_text(_requirement_name(requirement), 32)
    return [fallback] if fallback else []


def _candidate_skills(candidate_profile: dict[str, Any], resume_evidence: list[dict[str, Any]]) -> set[str]:
    skills: set[str] = set()
    for skill in candidate_profile.get("skills") or []:
        clean = _normalize(str(skill))
        if clean:
            skills.add(clean)
    for item in resume_evidence:
        for skill in item.get("normalized_skills") or []:
            clean = _normalize(str(skill))
            if clean:
                skills.add(clean)
    return skills


def _requirement_name(requirement: dict[str, Any]) -> str:
    return str(requirement.get("name") or requirement.get("description") or "").strip()


def _tailoring_section_name(item: dict[str, Any]) -> str:
    section = _normalize_section_name(item.get("section"))
    if section:
        return section

    evidence_type = _normalize_section_name(item.get("evidence_type"))
    return evidence_type or "projects"


def _evidence_ids_for_keywords(
    keywords: list[str],
    *,
    candidate_skills: set[str],
    resume_evidence: list[dict[str, Any]],
) -> list[str]:
    refs: list[str] = []
    for keyword in keywords:
        _, matched_refs = _keyword_matches_evidence(
            keyword,
            candidate_skills=candidate_skills,
            resume_evidence=resume_evidence,
        )
        refs.extend(matched_refs)
    return unique_strings(refs)


def _evidence_ids_for_sections(resume_evidence: list[dict[str, Any]], sections: set[str]) -> list[str]:
    refs: list[str] = []
    for item in resume_evidence:
        if _tailoring_section_name(item) not in sections:
            continue
        evidence_id = str(item.get("evidence_id") or "").strip()
        if evidence_id:
            refs.append(evidence_id)
    return unique_strings(refs)


def _keyword_matches_evidence(
    keyword: str,
    *,
    candidate_skills: set[str],
    resume_evidence: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    clean_keyword = _normalize(keyword)
    if not clean_keyword:
        return False, []

    evidence_refs: list[str] = []
    matched = clean_keyword in candidate_skills
    for item in resume_evidence:
        item_text = _normalize(str(item.get("text") or ""))
        item_skills = {_normalize(str(skill)) for skill in item.get("normalized_skills") or []}
        if clean_keyword in item_text or clean_keyword in item_skills:
            matched = True
            evidence_id = str(item.get("evidence_id") or "").strip()
            if evidence_id:
                evidence_refs.append(evidence_id)
    return matched, unique_strings(evidence_refs)


def _build_keyword_coverage(
    job_requirements: list[dict[str, Any]],
    candidate_skills: set[str],
    resume_evidence: list[dict[str, Any]],
) -> dict[str, list[str]]:
    covered: list[str] = []
    missing: list[str] = []
    overused: list[str] = []

    requirement_names: set[str] = set()
    for requirement in job_requirements:
        labels = _requirement_keywords(requirement)
        if not labels:
            continue
        requirement_names.update(_normalize(label) for label in labels)
        matched_any = False
        for label in labels:
            matched, _ = _keyword_matches_evidence(
                label,
                candidate_skills=candidate_skills,
                resume_evidence=resume_evidence,
            )
            if matched:
                covered.append(label)
                matched_any = True
            elif str(requirement.get("requirement_level") or "") == "must_have":
                missing.append(label)
        if matched_any:
            continue

    for skill in candidate_skills:
        if skill and skill not in requirement_names:
            overused.append(skill)

    return {
        "covered": unique_strings(covered)[:6],
        "missing": unique_strings(missing)[:6],
        "overused": unique_strings(overused)[:6],
    }


def _pick_source_resume_id(candidate_profile: dict[str, Any], resume_evidence: list[dict[str, Any]]) -> str:
    resume_id = str(candidate_profile.get("source_resume_id") or "").strip()
    if resume_id:
        return resume_id
    for item in resume_evidence:
        resume_id = str(item.get("resume_id") or "").strip()
        if resume_id:
            return resume_id
    return "resume::unknown"


def _project_or_experience_items(resume_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in resume_evidence
        if _tailoring_section_name(item) in {"projects", "work_experience"}
    ]


def _build_section_actions(
    *,
    keyword_coverage: dict[str, list[str]],
    candidate_skills: set[str],
    resume_evidence: list[dict[str, Any]],
) -> list[ResumeTailorSectionAction]:
    actions: list[ResumeTailorSectionAction] = []
    evidence_items = _project_or_experience_items(resume_evidence)

    for item in evidence_items[:2]:
        evidence_id = str(item.get("evidence_id") or "").strip()
        text = clip_text(str(item.get("text") or ""), 90)
        if not evidence_id or not text:
            continue
        section = _tailoring_section_name(item)
        actions.append(
            ResumeTailorSectionAction(
                section=section,
                action="rewrite",
                instruction=(
                    f"保留原始事实“{text}”，把表达重心放到目标岗位相关能力上，"
                    "不要补写原简历里没有出现的角色、指标或规模。"
                ),
                allowed_evidence_refs=[evidence_id],
            )
        )

    if keyword_coverage.get("covered") or keyword_coverage.get("missing"):
        allowed_refs = _evidence_ids_for_keywords(
            (keyword_coverage.get("covered") or [])[:3],
            candidate_skills=candidate_skills,
            resume_evidence=resume_evidence,
        )
        if not allowed_refs:
            allowed_refs = _evidence_ids_for_sections(resume_evidence, {"projects", "work_experience"})
        actions.append(
            ResumeTailorSectionAction(
                section="skills",
                action="prioritize",
                instruction=(
                    f"把 {', '.join((keyword_coverage.get('covered') or [])[:3]) or '已出现的技能'} 前置到技能摘要中；"
                    f"缺失的 {', '.join((keyword_coverage.get('missing') or [])[:2]) or '高权重要求'} 只作为补充建议，"
                    "不要把“会”写成“精通”。"
                ),
                allowed_evidence_refs=allowed_refs,
            )
        )

    return actions


def _build_headline(keyword_coverage: dict[str, list[str]], target_role: str) -> str:
    covered = keyword_coverage.get("covered") or []
    if covered:
        return f"具备 {', '.join(covered[:3])} 项目经验的{target_role or '目标岗位'}候选人"
    return f"{target_role or '目标岗位'}候选人，简历应优先保留可被原始证据支持的经历"


def _build_summary_text(headline: str, keyword_coverage: dict[str, list[str]]) -> str:
    covered = keyword_coverage.get("covered") or []
    if covered:
        return f"{headline}，建议优先突出 {', '.join(covered[:3])} 相关事实，并保持原始经历边界清晰。"
    return f"{headline}，当前只做保守重排，不补写任何未在原始简历中出现的内容。"


def _build_project_bullets(resume_evidence: list[dict[str, Any]]) -> list[str]:
    bullets: list[str] = []
    for item in _project_or_experience_items(resume_evidence):
        text = clip_text(str(item.get("text") or ""), 120)
        if text:
            bullets.append(text)
    return unique_strings(bullets)[:4]


def _build_omissions(
    *,
    resume_evidence: list[dict[str, Any]],
    keyword_coverage: dict[str, list[str]],
) -> list[str]:
    omissions: list[str] = []
    if keyword_coverage.get("missing"):
        omissions.append(f"缺失要求 {', '.join(keyword_coverage.get('missing') or [])} 只作为补充建议，不写成已掌握事实。")
    if len(_project_or_experience_items(resume_evidence)) > 2:
        omissions.append("其余非核心经历可压缩到次级位置，避免稀释与岗位强相关的项目事实。")
    return unique_strings(omissions)[:3]


def _target_role(job_posting: dict[str, Any], candidate_profile: dict[str, Any]) -> str:
    job_role = str(job_posting.get("job_title") or "").strip()
    if job_role:
        return job_role
    target_roles = candidate_profile.get("target_roles") or []
    if target_roles:
        return str(target_roles[0]).strip()
    return ""


def _build_fact_check_report(
    *,
    resume_version_id: str,
    blocked_claims: list[str],
    created_at: str,
) -> FactCheckReport:
    status = "downgraded" if blocked_claims else "passed"
    return FactCheckReport(
        verification_id=f"ver::{resume_version_id}",
        artifact_type="resume_version",
        artifact_id=resume_version_id,
        status=status,
        blocked_claims=blocked_claims,
        checked_rules=[
            "candidate_fact_boundary",
            "evidence_coverage",
            "keyword_coverage",
            "recommendation_clarity",
        ],
        created_at=created_at,
    )


def build_resume_tailoring_artifacts(
    *,
    candidate_profile: dict[str, Any],
    resume_evidence: list[dict[str, Any]],
    job_snapshot: dict[str, Any],
    match_assessment: dict[str, Any],
) -> dict[str, Any]:
    candidate_profile = dict(candidate_profile or {})
    resume_evidence = list(resume_evidence or [])
    job_snapshot = dict(job_snapshot or {})
    match_assessment = dict(match_assessment or {})

    if not candidate_profile and not resume_evidence:
        return {}

    if not candidate_profile or not resume_evidence:
        raise ValueError("tailoring inputs require both candidate_profile and resume_evidence")

    candidate_id = str(candidate_profile.get("candidate_id") or "").strip()
    if not candidate_id:
        raise ValueError("tailoring inputs must include candidate_profile.candidate_id")

    if not match_assessment:
        raise ValueError("tailoring inputs must include match_assessment")

    for index, item in enumerate(resume_evidence, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"resume_evidence[{index}] must be an object")
        evidence_id = str(item.get("evidence_id") or "").strip()
        if not evidence_id:
            raise ValueError(f"resume_evidence[{index}] must include evidence_id")
        section = str(item.get("section") or item.get("evidence_type") or "").strip()
        if not section:
            raise ValueError(f"resume_evidence[{index}] must include section or evidence_type")

    job_id = str(job_snapshot.get("job_id") or "").strip()
    if not job_id:
        raise ValueError("tailoring inputs must include job_snapshot.job_id")

    job_posting = dict(job_snapshot.get("job_posting") or {})
    job_requirements = list(job_snapshot.get("job_requirements") or [])
    target_role = _target_role(job_posting, candidate_profile)
    candidate_skills = _candidate_skills(candidate_profile, resume_evidence)
    keyword_coverage = _build_keyword_coverage(job_requirements, candidate_skills, resume_evidence)
    headline = _build_headline(keyword_coverage, target_role)
    section_actions = _build_section_actions(
        keyword_coverage=keyword_coverage,
        candidate_skills=candidate_skills,
        resume_evidence=resume_evidence,
    )
    source_resume_id = _pick_source_resume_id(candidate_profile, resume_evidence)
    resume_version_id = f"resume::{candidate_id}::{job_id}"
    created_at = utc_now_iso()
    blocked_claims = [
        f'未将缺失要求 "{keyword}" 写成已掌握事实'
        for keyword in keyword_coverage.get("missing") or []
    ]
    fact_check_report = _build_fact_check_report(
        resume_version_id=resume_version_id,
        blocked_claims=blocked_claims,
        created_at=created_at,
    )
    tailor_plan = ResumeTailoringPlan(
        tailor_plan_id=f"rtp::{candidate_id}::{job_id}",
        candidate_id=candidate_id,
        job_id=job_id,
        target_role=target_role,
        headline_suggestion=headline,
        keyword_coverage=keyword_coverage,
        section_actions=section_actions,
        risk_notes=[
            "不得补写未在原始简历出现的数字成果。",
            "缺失关键词应保留为补充建议，不要写成已掌握能力。",
        ],
    )
    resume_version = ResumeVersion(
        resume_version_id=resume_version_id,
        candidate_id=candidate_id,
        job_id=job_id,
        source_resume_id=source_resume_id,
        version_label=f"{candidate_id}::{job_id}::tailored",
        summary_text=_build_summary_text(headline, keyword_coverage),
        project_bullets=_build_project_bullets(resume_evidence),
        keyword_insertions=unique_strings((keyword_coverage.get("covered") or [])[:4]),
        omissions=_build_omissions(resume_evidence=resume_evidence, keyword_coverage=keyword_coverage),
        fact_check_status=fact_check_report.status,
        created_at=created_at,
    )
    return {
        "tailor_plan": tailor_plan.model_dump(mode="json"),
        "resume_version": resume_version.model_dump(mode="json"),
        "fact_check_report": fact_check_report.model_dump(mode="json"),
    }


async def resume_tailor_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    candidate_profile = dict(state.get("candidate_profile") or {})
    resume_evidence = list(state.get("resume_evidence") or [])
    job_snapshot = dict(state.get("job_snapshot") or {})
    match_assessment = dict(state.get("match_assessment") or {})

    artifacts = build_resume_tailoring_artifacts(
        candidate_profile=candidate_profile,
        resume_evidence=resume_evidence,
        job_snapshot=job_snapshot,
        match_assessment=match_assessment,
    )
    if not artifacts:
        return {
            "tailor_plan": {},
            "resume_version": {},
            "fact_check_report": {},
            "status": "✍️ ResumeTailorAgent 未生成简历定制产物：缺少 JobSnapshot 或 MatchAssessment。",
        }

    return {
        **artifacts,
        "status": "✍️ ResumeTailorAgent 已生成简历定制计划、岗位版本和事实校验结果。",
    }
