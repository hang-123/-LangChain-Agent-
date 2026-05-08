"""ResumeParser Tool — parse resume files (PDF/DOCX/TXT) into CandidateProfile + ResumeEvidence.
Single LLM call for text extraction. Deterministic validation afterward."""

from __future__ import annotations

from typing import Any

from api.core.harness import utc_now_iso


def _extract_raw_text(source_type: str, raw_text: str, content_bytes: bytes | None) -> str:
    """Extract raw text from resume file. Phase 2: basic handling."""
    if raw_text.strip():
        return raw_text.strip()

    if content_bytes:
        try:
            text = content_bytes.decode("utf-8", errors="replace")
            if text.strip():
                return text.strip()
        except Exception:
            pass

    return ""


def _compute_profile_completeness(
    candidate_profile: dict[str, Any],
    resume_evidence: list[dict[str, Any]],
) -> float:
    """Compute 0-1 completeness score."""
    required_fields = ["name", "skills", "education"]
    if not isinstance(candidate_profile, dict):
        return 0.0

    filled = sum(1 for f in required_fields if candidate_profile.get(f))
    profile_score = filled / len(required_fields)

    evidence_score = min(1.0, len(resume_evidence) / 3.0) if resume_evidence else 0.0
    return round(profile_score * 0.6 + evidence_score * 0.4, 2)


async def _llm_extract(raw_text: str) -> dict[str, Any]:
    """Single LLM call to extract structured info from resume text."""
    from api.core.llm import invoke_structured_output
    from pydantic import BaseModel, Field

    class ResumeExtraction(BaseModel):
        name: str = ""
        email: str = ""
        phone: str = ""
        education: list[dict[str, str]] = Field(default_factory=list)
        skills: list[str] = Field(default_factory=list)
        work_experience: list[dict[str, Any]] = Field(default_factory=list)
        projects: list[dict[str, Any]] = Field(default_factory=list)
        certificates: list[str] = Field(default_factory=list)
        target_roles: list[str] = Field(default_factory=list)
        location_preferences: list[str] = Field(default_factory=list)
        years_of_experience: float = 0.0

    try:
        result = await invoke_structured_output(
            ResumeExtraction,
            system_prompt=(
                "你是简历解析器。从原始简历文本中提取结构化信息。"
                "只提取明确写出的信息，不要推测。"
                "技能名标准化（如'java'→'Java'）。"
                "不要把课程名自动提升为'熟练掌握'。"
                "项目与实习经历都拆成独立证据项。"
            ),
            human_prompt="简历文本：\n{text}\n\n请提取结构化信息。",
            variables={"text": raw_text[:8000]},
            temperature=0.1,
        )
        return result.model_dump()
    except Exception:
        return {"name": "", "skills": [], "education": []}


def _build_resume_evidence(extracted: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert extracted fields into ResumeEvidence items."""
    evidence: list[dict[str, Any]] = []
    eid = 0

    for exp in extracted.get("work_experience", []):
        eid += 1
        evidence.append({
            "evidence_id": f"ev_resume_{eid}",
            "section": "work_experience",
            "evidence_type": "work_experience",
            "text": str(exp.get("description", exp.get("company", ""))),
            "normalized_skills": [],
            "start_date": str(exp.get("start_date", "")),
            "end_date": str(exp.get("end_date", "")),
        })

    for proj in extracted.get("projects", []):
        eid += 1
        evidence.append({
            "evidence_id": f"ev_resume_{eid}",
            "section": "projects",
            "evidence_type": "project",
            "text": str(proj.get("description", proj.get("name", ""))),
            "normalized_skills": [],
        })

    return evidence


async def run_resume_parser(state: dict[str, Any]) -> dict[str, Any]:
    """ResumeParser Tool — parse resume and produce CandidateProfile + ResumeEvidence."""
    source_type = str(state.get("resume_source_type") or "txt")
    raw_text = str(state.get("resume_raw_text") or "")
    content_bytes = state.get("resume_content_bytes")
    source_name = str(state.get("resume_source_name") or "unknown")

    # If candidate_profile already exists, skip parsing
    existing_profile = dict(state.get("candidate_profile") or {})
    if existing_profile.get("candidate_id") and state.get("skip_parse"):
        return {
            "candidate_profile": existing_profile,
            "resume_evidence": state.get("resume_evidence", []),
            "profile_completeness": 0.8,
            "profile_gaps": [],
            "warnings": [],
            "status": "已有结构化画像，跳过解析。",
        }

    # Extract raw text
    text = _extract_raw_text(source_type, raw_text, content_bytes)

    if len(text.strip()) < 100:
        return {
            "candidate_profile": {},
            "resume_evidence": [],
            "profile_completeness": 0.1,
            "profile_gaps": ["文本过短，无法完整解析"],
            "warnings": ["insufficient_text"],
            "status": "ResumeParser 简历文本过短(<100字符)，无法完整解析。",
        }

    # LLM extraction
    extracted = await _llm_extract(text)
    resume_evidence = _build_resume_evidence(extracted)

    # Build candidate profile
    candidate_id = f"cand::{extracted.get('name', 'unknown')}::{utc_now_iso()[:10]}"
    candidate_profile = {
        "candidate_id": candidate_id,
        "name": extracted.get("name", ""),
        "email": extracted.get("email", ""),
        "phone": extracted.get("phone", ""),
        "skills": extracted.get("skills", []),
        "education": extracted.get("education", []),
        "target_roles": extracted.get("target_roles", []),
        "location_preferences": extracted.get("location_preferences", []),
        "years_of_experience": extracted.get("years_of_experience", 0.0),
    }

    # Compute completeness
    completeness = _compute_profile_completeness(candidate_profile, resume_evidence)
    profile_gaps: list[str] = []
    if not extracted.get("name"):
        profile_gaps.append("缺少姓名")
    if not extracted.get("skills"):
        profile_gaps.append("缺少技能信息")
    if not extracted.get("education"):
        profile_gaps.append("缺少教育信息")

    warnings: list[str] = []
    if completeness < 0.5:
        warnings.append("profile_completeness_below_threshold")

    return {
        "candidate_profile": candidate_profile,
        "resume_evidence": resume_evidence,
        "profile_completeness": completeness,
        "profile_gaps": profile_gaps,
        "warnings": warnings,
        "status": f"ResumeParser 完成解析，完整度: {completeness:.2f}",
    }
