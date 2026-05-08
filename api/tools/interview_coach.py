"""InterviewCoach Tool — generate personalized interview prep materials.
Single LLM call for question generation."""

from __future__ import annotations

from typing import Any

from api.core.harness import utc_now_iso


async def run_interview_coach(state: dict[str, Any]) -> dict[str, Any]:
    """InterviewCoach Tool — generate interview questions and prep framework."""
    from api.core.llm import invoke_structured_output
    from pydantic import BaseModel, Field

    candidate_profile = dict(state.get("candidate_profile") or {})
    resume_evidence = list(state.get("resume_evidence") or [])
    job_snapshot = dict(state.get("job_snapshot") or {})
    match_assessment = dict(state.get("match_assessment") or {})

    # Validation
    if not candidate_profile:
        return {
            "prep_pack": {},
            "status": "InterviewCoach 需要候选人画像，请先解析简历。",
        }
    if not match_assessment:
        return {
            "prep_pack": {},
            "status": "InterviewCoach 需要匹配评估结果，请先运行岗位匹配。",
        }

    class InterviewQuestion(BaseModel):
        question: str = ""
        category: str = "behavioral"  # behavioral / technical / project_deep_dive
        difficulty: str = "medium"
        evidence_refs: list[str] = Field(default_factory=list)
        answer_framework: str = ""

    class InterviewPrepOutput(BaseModel):
        behavioral_questions: list[InterviewQuestion] = Field(default_factory=list)
        technical_questions: list[InterviewQuestion] = Field(default_factory=list)
        project_deep_dive: list[InterviewQuestion] = Field(default_factory=list)
        risk_questions: list[InterviewQuestion] = Field(default_factory=list)
        practice_advice: list[str] = Field(default_factory=list)

    # Build input context
    strengths = match_assessment.get("strengths", [])
    gaps = match_assessment.get("gaps", [])
    risks = match_assessment.get("risks", [])

    job_posting = job_snapshot.get("job_posting", {})
    job_requirements = job_snapshot.get("job_requirements", [])
    must_have_reqs = [r for r in job_requirements if r.get("requirement_level") == "must_have"]
    req_names = [r.get("name", r.get("description", "")) for r in must_have_reqs[:5]]
    project_evidence = [e for e in resume_evidence if e.get("section") in ("projects", "project")]
    candidate_summary = f"候选人技能: {', '.join(candidate_profile.get('skills', [])[:8])}"

    try:
        result = await invoke_structured_output(
            InterviewPrepOutput,
            system_prompt=(
                "你是面试准备教练。基于候选人真实经历和目标岗位要求，生成个性化面试准备材料。\n\n"
                "出题规则：\n"
                "- 问题优先覆盖高权重 must_have 要求\n"
                "- 项目深挖题必须绑定候选人真实项目证据\n"
                "- 对匹配分析中的高风险项，必须生成至少一个追问题\n"
                "- 回答框架使用'背景-任务-方案-结果-复盘'结构\n"
                "- 不要生成标准答案式虚构经历\n"
                "- 不要把面试问题伪装成真实公司题库\n"
            ),
            human_prompt=(
                f"目标岗位要求：\n{chr(10).join(req_names[:8])}\n\n"
                f"候选人概况：\n{candidate_summary}\n\n"
                f"匹配优势：\n{chr(10).join(s.get('title','') for s in strengths[:3])}\n\n"
                f"匹配差距：\n{chr(10).join(g.get('title','') for g in gaps[:3])}\n\n"
                f"风险点：\n{chr(10).join(r.get('title','') for r in risks[:3])}\n\n"
                f"候选人项目经历：\n{chr(10).join(e.get('text','')[:200] for e in project_evidence[:3])}\n\n"
                "请生成面试准备包。"
            ),
            variables={},
            temperature=0.5,
        )
    except Exception:
        return {
            "prep_pack": {},
            "status": "InterviewCoach LLM调用失败，请重试。",
        }

    candidate_id = candidate_profile.get("candidate_id", "unknown")
    job_id = job_snapshot.get("job_id", "unknown")
    prep_pack = {
        "prep_id": f"ipp::{candidate_id}::{job_id}",
        "candidate_id": candidate_id,
        "job_id": job_id,
        "behavioral_questions": [q.model_dump() for q in result.behavioral_questions],
        "technical_questions": [q.model_dump() for q in result.technical_questions],
        "project_deep_dive": [q.model_dump() for q in result.project_deep_dive],
        "risk_questions": [q.model_dump() for q in result.risk_questions],
        "practice_advice": result.practice_advice,
        "created_at": utc_now_iso(),
    }

    return {
        "prep_pack": prep_pack,
        "interview_prep_pack": prep_pack,
        "status": f"InterviewCoach 已生成面试准备包，含{len(result.behavioral_questions)}行为题+{len(result.technical_questions)}技术题+{len(result.project_deep_dive)}项目深挖题。",
    }
