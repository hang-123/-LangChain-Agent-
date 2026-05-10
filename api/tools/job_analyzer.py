"""JobAnalyzer Tool — JD parsing + external evidence + archetype + legitimacy.
Merges JobIntelligenceAgent + ArchetypeDetector + LegitimacyScorer into one Tool.
LLM: 1 call (if raw_jd_text provided) + optional archetype confirmation."""

from __future__ import annotations

from typing import Any

from api.core.settings import get_settings

# Reuse existing components
from api.agents.archetype_detector import (
    _detect_from_keywords,
    _llm_confirm_archetype,
    DEFAULT_FRAMING,
)
from api.agents.legitimacy_scorer import (
    _check_expired_patterns,
    _check_requirements_realism,
    _compute_tech_specificity,
    _extract_layoff_signals,
)
from api.core.contracts import (
    ArchetypeDetection,
    LegitimacyAssessment,
    LegitimacySignal,
    LegitimacyTier,
)
from api.core.harness import utc_now_iso


async def _parse_jd_text(raw_jd_text: str) -> dict[str, Any]:
    """Single LLM call to parse raw JD text into structured requirements."""
    from api.core.llm import invoke_structured_output
    from pydantic import BaseModel, Field

    class JDParsed(BaseModel):
        company_name: str = ""
        job_title: str = ""
        requirements: list[dict[str, Any]] = Field(default_factory=list)
        salary_range: str = ""
        location: str = ""
        description: str = ""

    try:
        result = await invoke_structured_output(
            JDParsed,
            system_prompt=(
                "你是JD解析器。从原始职位描述中提取结构化信息。"
                "每条requirement需包含: name, description, requirement_level(must_have/nice_to_have/bonus), evidence_text。"
                "不要推测，只提取明确写出的信息。"
            ),
            human_prompt="原始JD文本：\n{text}\n\n请提取结构化信息。",
            variables={"text": raw_jd_text[:6000]},
            temperature=0.1,
        )
        return result.model_dump()
    except Exception:
        return {"company_name": "", "job_title": "", "requirements": [], "salary_range": "", "location": "", "description": raw_jd_text[:500]}


def _build_job_snapshot(
    parsed_jd: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    archetype_detection: dict[str, Any],
    legitimacy_assessment: dict[str, Any],
) -> dict[str, Any]:
    """Assemble a JobSnapshot from all components."""
    job_id = f"job::{parsed_jd.get('company_name', 'unknown')}::{parsed_jd.get('job_title', 'unknown')}"
    job_requirements = list(parsed_jd.get("requirements", []))

    # If no JD parsing, extract requirements from evidence
    if not job_requirements and evidence_items:
        job_requirements = [
            {
                "requirement_id": f"req_infer_{i}",
                "name": e.get("title", f"要求{i+1}"),
                "description": e.get("snippet", "")[:200],
                "requirement_level": "nice_to_have",
                "evidence_text": e.get("snippet", "")[:200],
            }
            for i, e in enumerate(evidence_items[:5])
        ]

    return {
        "job_snapshot_id": f"js_{job_id}",
        "job_id": job_id,
        "job_posting": {
            "company_name": parsed_jd.get("company_name", ""),
            "job_title": parsed_jd.get("job_title", ""),
            "description": parsed_jd.get("description", ""),
            "salary_range": parsed_jd.get("salary_range", ""),
            "location": parsed_jd.get("location", ""),
        },
        "job_requirements": job_requirements,
        "external_evidence_pack_id": f"jep_{job_id}",
        "evidence_quality": {
            "freshness": "unknown",
            "coverage": "partial" if evidence_items else "minimal",
            "ambiguity_notes": [] if parsed_jd.get("company_name") else ["未基于真实JD，由证据推断"],
        },
    }


def _build_legitimacy_assessment(  # noqa: C901
    all_text: str,
    evidence_items: list[dict[str, Any]],
    jd_text: str,
) -> dict[str, Any]:
    """Run deterministic legitimacy scoring (0 LLM)."""
    import re
    signals: list[dict[str, Any]] = []
    positive_count = 0
    concerning_count = 0

    # Signal 1: Expired patterns
    expired_match = _check_expired_patterns(all_text)
    if expired_match:
        signals.append({"signal_name": "expired_pattern", "finding": f"匹配到已过期模式: {expired_match[:80]}", "weight": "Concerning", "reliability": "High"})
        concerning_count += 1
    elif all_text.strip():
        signals.append({"signal_name": "expired_pattern", "finding": "未检测到过期模式。", "weight": "Neutral", "reliability": "High"})

    # Signal 2: Tech specificity
    specificity = _compute_tech_specificity(all_text)
    if specificity >= 0.08:
        signals.append({"signal_name": "tech_specificity", "finding": f"高技术特异性({specificity:.2f})。", "weight": "Positive", "reliability": "Medium"})
        positive_count += 1
    elif specificity >= 0.03:
        signals.append({"signal_name": "tech_specificity", "finding": f"中等技术特异性({specificity:.2f})。", "weight": "Neutral", "reliability": "Medium"})
    else:
        signals.append({"signal_name": "tech_specificity", "finding": f"低技术特异性({specificity:.2f})，JD使用通用语言。", "weight": "Concerning", "reliability": "Medium"})
        concerning_count += 1

    # Signal 3: Requirements realism
    realism_score, realism_warnings = _check_requirements_realism(all_text)
    if realism_score >= 0.9:
        signals.append({"signal_name": "requirements_realism", "finding": "未检测到不现实的要求。", "weight": "Positive", "reliability": "Medium"})
        positive_count += 1
    else:
        signals.append({"signal_name": "requirements_realism", "finding": f"可能有不现实要求: {'; '.join(realism_warnings[:3])}", "weight": "Concerning", "reliability": "Medium"})
        concerning_count += 1

    # Signal 4: Layoff signals
    layoff_signals = _extract_layoff_signals(evidence_items)
    if layoff_signals:
        signals.append({"signal_name": "layoff_news", "finding": f"发现裁员信号: {'; '.join(layoff_signals[:3])}", "weight": "Concerning", "reliability": "Medium"})
        concerning_count += 1
    else:
        signals.append({"signal_name": "layoff_news", "finding": "未检测到裁员信号。", "weight": "Neutral", "reliability": "Medium"})

    # Signal 5: Content sufficiency
    if len(all_text.strip()) < 300:
        signals.append({"signal_name": "content_sufficiency", "finding": f"内容过少({len(all_text.strip())}字符)。", "weight": "Concerning", "reliability": "High"})
        concerning_count += 1
    else:
        signals.append({"signal_name": "content_sufficiency", "finding": f"内容充足({len(all_text.strip())}字符)。", "weight": "Positive", "reliability": "High"})
        positive_count += 1

    # Determine tier
    if concerning_count >= 3 or expired_match:
        tier = "Suspicious"
        context_notes = "多个可疑信号。投递前建议确认岗位仍开放。"
    elif concerning_count >= 1:
        tier = "Proceed with Caution"
        context_notes = "混合信号，建议留意但不影响投递。"
    else:
        tier = "High Confidence"
        context_notes = "多数信号积极，很可能为真实开放岗位。"

    if not jd_text:
        context_notes += " JD文本有限（batch模式或抓取失败）。"

    return {
        "tier": tier,
        "tech_specificity_score": round(specificity, 3),
        "requirements_realism_score": round(realism_score, 2),
        "layoff_signals": layoff_signals,
        "signals_table": signals,
        "context_notes": context_notes,
        "batch_mode": not bool(jd_text),
    }


def _dedupe_nonempty(items: list[str], *, limit: int = 4) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        clean = str(item or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
        if len(result) >= limit:
            break
    return result


def _extract_external_signals(
    evidence_items: list[dict[str, Any]],
    job_snapshot: dict[str, Any],
    legitimacy_assessment: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    company_signals: list[str] = []
    interview_signals: list[str] = []
    risk_flags: list[str] = []

    ambiguity_notes = list((job_snapshot.get("evidence_quality") or {}).get("ambiguity_notes") or [])
    risk_flags.extend(str(note) for note in ambiguity_notes if str(note).strip())

    tier = str(legitimacy_assessment.get("tier") or "")
    if tier == "Suspicious":
        risk_flags.append("岗位合法性存在明显风险，建议投递前二次确认。")
    elif tier == "Proceed with Caution":
        risk_flags.append("岗位信号混合，建议结合官网或 HR 信息再确认。")

    for signal in legitimacy_assessment.get("layoff_signals") or []:
        risk_flags.append(str(signal))

    for item in evidence_items:
        source_class = str(item.get("source_class") or "")
        title = str(item.get("title") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        text = title or snippet
        if not text:
            continue
        if source_class in {"company_profile", "salary_culture", "tech_stack"}:
            company_signals.append(text[:80])
        if source_class == "interview":
            interview_signals.append(text[:80])

    return (
        _dedupe_nonempty(company_signals),
        _dedupe_nonempty(interview_signals),
        _dedupe_nonempty(risk_flags),
    )


async def run_job_analyzer(state: dict[str, Any]) -> dict[str, Any]:
    """JobAnalyzer Tool — unified job analysis entry point."""
    settings = get_settings()
    query_profile = dict(state.get("query_profile") or {})
    evidence_items = list(state.get("evidence_items") or [])
    raw_jd_text = str(state.get("raw_jd_text") or "")
    context = list(state.get("context") or [])

    # Step 1: Parse JD if available
    parsed_jd: dict[str, Any] = {}
    if raw_jd_text.strip():
        parsed_jd = await _parse_jd_text(raw_jd_text)
    else:
        # Infer from query_profile
        parsed_jd = {
            "company_name": query_profile.get("company", ""),
            "job_title": query_profile.get("role", ""),
            "requirements": [],
            "salary_range": "",
            "location": "",
            "description": "",
        }

    # Step 2: Collect text for analysis
    jd_text = raw_jd_text or parsed_jd.get("description", "")
    all_text = " ".join([jd_text] + [str(c)[:500] for c in context[:5]])

    # Step 3: Archetype detection
    if settings.enable_archetype_detector and all_text.strip():
        detection = _detect_from_keywords(all_text)
        if detection.confidence < 0.7 and jd_text:
            detection = await _llm_confirm_archetype(all_text, detection)
        archetype_detection = detection.model_dump()
        framing = DEFAULT_FRAMING.get(detection.primary, DEFAULT_FRAMING[detection.primary])
        adaptive_framing = framing.model_dump() if framing else {}
    else:
        archetype_detection = {"primary": "AI Platform / LLMOps", "confidence": 0.0, "reasoning": "文本不足"}
        adaptive_framing = {}

    # Step 4: Legitimacy assessment
    if settings.enable_legitimacy_scorer:
        legitimacy_assessment = _build_legitimacy_assessment(all_text, evidence_items, jd_text)
    else:
        legitimacy_assessment = {"tier": "High Confidence", "batch_mode": True}

    # Step 5: Build JobSnapshot
    job_snapshot = _build_job_snapshot(
        parsed_jd, evidence_items, archetype_detection, legitimacy_assessment,
    )

    # Build ExternalEvidencePack from evidence_items
    company_signals, interview_signals, risk_flags = _extract_external_signals(
        evidence_items,
        job_snapshot,
        legitimacy_assessment,
    )

    external_evidence_pack = {
        "evidence_pack_id": f"jep_{job_snapshot['job_id']}",
        "job_id": job_snapshot["job_id"],
        "sources": [
            {
                "source_id": e.get("source_id", f"src_{i}"),
                "source_type": e.get("source_class", "unknown"),
                "title": e.get("title", ""),
                "url": e.get("url", ""),
                "snippet": e.get("snippet", ""),
            }
            for i, e in enumerate(evidence_items[:10])
        ],
        "company_signals": company_signals,
        "interview_signals": interview_signals,
        "risk_flags": risk_flags,
    }

    # Phase 2: working memory entry
    working_memory = list(state.get("working_memory") or [])
    working_memory.append({
        "source": "job_analyzer",
        "summary": {
            "job_snapshot_id": job_snapshot.get("job_snapshot_id", ""),
            "job_id": job_snapshot.get("job_id", ""),
            "requirement_count": len(job_snapshot.get("job_requirements", [])),
            "archetype": str(archetype_detection.get("primary", "")),
            "legitimacy_tier": str(legitimacy_assessment.get("tier", "")),
            "has_external_evidence": bool(external_evidence_pack.get("sources")),
        },
        "timestamp": utc_now_iso(),
    })

    return {
        "job_snapshot": job_snapshot,
        "external_evidence_pack": external_evidence_pack,
        "archetype_detection": archetype_detection,
        "legitimacy_assessment": legitimacy_assessment,
        "adaptive_framing": adaptive_framing,
        "working_memory": working_memory,
        "status": f"JobAnalyzer 完成岗位分析，合法性: {legitimacy_assessment.get('tier', 'unknown')}",
    }
