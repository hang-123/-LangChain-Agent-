"""OfferEvaluator — integrates archetype + legitimacy results into enhanced evaluation.

Takes the outputs from:
  - MatchingAgent (match scores, strengths, gaps, risks)
  - ArchetypeDetector (archetype + adaptive framing)
  - LegitimacyScorer (posting legitimacy assessment)

Produces enhanced evaluation with:
  - Gap analysis (4-level classification)
  - Level strategy (sell seniority without lying)
  - STAR+R story mapping hints
  - Score interpretation aligned with career-ops thresholds
"""

from __future__ import annotations

from typing import Any

from api.core.contracts import (
    Archetype,
    ArchetypeDetection,
    GapSeverity,
    LegitimacyAssessment,
    MatchGap,
)

# -- Score interpretation (from career-ops _shared.md) --


def interpret_score(score: float) -> dict[str, Any]:
    """Map a 0-5 score to career-ops interpretation and recommendation."""
    if score >= 4.5:
        return {
            "tier": "strong_match",
            "recommendation": "Strong match — recommend applying immediately.",
            "apply": True,
            "draft_answers": True,
        }
    elif score >= 4.0:
        return {
            "tier": "good_match",
            "recommendation": "Good match — worth applying.",
            "apply": True,
            "draft_answers": False,
        }
    elif score >= 3.5:
        return {
            "tier": "decent_match",
            "recommendation": "Decent but not ideal — apply only if you have a specific reason.",
            "apply": False,
            "draft_answers": False,
        }
    else:
        return {
            "tier": "weak_match",
            "recommendation": "Below threshold — recommend against applying.",
            "apply": False,
            "draft_answers": False,
        }


# -- Gap analysis --


def classify_gap(
    gap_desc: str,
    candidate_has_adjacent: bool = False,
    portfolio_covers: bool = False,
) -> MatchGap:
    """Classify a gap into one of 4 severity levels.

    Algorithm from career-ops oferta.md:
    1. Is it a strict requirement (years, certification, citizenship)?
    2. Does the candidate have adjacent/transferable experience?
    3. Is there a portfolio project that demonstrates similar capability?
    4. Can a quick project fill the gap before the interview?
    """
    lower = gap_desc.lower()

    # Hard blockers: legal, citizenship, strict certification, explicit "must have X years"
    hard_blocker_keywords = [
        "citizenship", "security clearance", "must be", "required certification",
        "licensed", "bar admission", "medical license",
    ]
    if any(kw in lower for kw in hard_blocker_keywords):
        return MatchGap(
            description=gap_desc,
            severity=GapSeverity.HARD_BLOCKER,
            mitigation_plan="Cannot be mitigated — hard requirement.",
        )

    # Significant: core skill gap, specific tech stack mismatch
    significant_keywords = [
        "experience with", "proficiency in", "expert in", "deep knowledge",
        "strong background", "track record",
    ]
    if any(kw in lower for kw in significant_keywords):
        if candidate_has_adjacent:
            return MatchGap(
                description=gap_desc,
                severity=GapSeverity.SIGNIFICANT,
                adjacent_experience="Candidate has transferable adjacent experience.",
                mitigation_plan="Frame adjacent experience as direct preparation. "
                "Highlight speed of learning with concrete examples.",
            )
        if portfolio_covers:
            return MatchGap(
                description=gap_desc,
                severity=GapSeverity.SIGNIFICANT,
                portfolio_coverage="Portfolio project demonstrates similar capability.",
                mitigation_plan="Present portfolio project as evidence. "
                "Prepare to discuss design decisions and trade-offs.",
            )
        return MatchGap(
            description=gap_desc,
            severity=GapSeverity.SIGNIFICANT,
            mitigation_plan="Consider a focused 2-week project to build demonstrable skill. "
            "Use adjacent experience as bridge in cover letter.",
        )

    # Nice-to-have: "bonus points", "nice to have", "familiarity with"
    nice_keywords = ["nice to have", "bonus", "familiarity", "plus", "preferred"]
    if any(kw in lower for kw in nice_keywords):
        return MatchGap(
            description=gap_desc,
            severity=GapSeverity.NICE_TO_HAVE,
            mitigation_plan="Mention awareness/familiarity if true. "
            "Not a blocker for application.",
        )

    # Soft: everything else
    return MatchGap(
        description=gap_desc,
        severity=GapSeverity.SOFT,
        mitigation_plan="Low priority. Address only if prompted in interview.",
    )


# -- Level strategy --


def build_level_strategy(
    jd_level_hint: str,
    candidate_natural_level: str = "Senior/Staff",
) -> dict[str, Any]:
    """Build level positioning strategy (Block C from career-ops).

    'Sell seniority without lying' approach:
    - Frame founder experience as leadership
    - Position breadth as strategic advantage
    - Always have a 'downgrade acceptance' plan
    """
    strategy = {
        "detected_jd_level": jd_level_hint,
        "candidate_natural_level": candidate_natural_level,
        "positioning": "",
        "downgrade_plan": "",
    }

    level_phrases: dict[str, str] = {
        "Senior/Staff": (
            "When you've built and sold a company, you've been the CTO, the PM, "
            "and the IC. You understand why decisions matter, not just how to execute. "
            "Frame depth through breadth — your cross-stack experience means you "
            "debug systemic issues faster than specialists."
        ),
        "Mid-Senior": (
            "Focus on execution velocity and end-to-end ownership. "
            "Highlight concrete shipped products with measurable impact."
        ),
        "Mid": (
            "Emphasize growth trajectory and appetite for ownership. "
            "Show evidence of operating above current level."
        ),
    }
    strategy["positioning"] = level_phrases.get(candidate_natural_level, level_phrases["Mid"])

    strategy["downgrade_plan"] = (
        "If offered at a lower level: accept ONLY if (1) compensation is fair for the level, "
        "(2) there is a written 6-month review with clear promotion criteria, "
        "(3) the role scope matches your target level in practice even if title doesn't."
    )

    return strategy


# -- Main node --


async def offer_evaluator_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: produce enhanced evaluation integrating all career-ops signals.

    Reads:
      - state["match_assessment"] (from MatchingAgent)
      - state["archetype_detection"] (from ArchetypeDetector)
      - state["adaptive_framing"] (from ArchetypeDetector)
      - state["legitimacy_assessment"] (from LegitimacyScorer)
      - state["insights"] (from InsightAgent — for action plan)
    Writes:
      - state["offer_evaluation"] — enhanced evaluation result
      - state["gap_analysis"] — list of MatchGap
      - state["level_strategy"] — level positioning strategy
      - state["score_interpretation"] — score tier + recommendation
    """
    match_assessment = dict(state.get("match_assessment") or {})
    archetype_detection_raw = dict(state.get("archetype_detection") or {})
    legitimacy_raw = dict(state.get("legitimacy_assessment") or {})
    candidate_profile = dict(state.get("candidate_profile") or {})
    resume_evidence = list(state.get("resume_evidence") or [])

    # -- Score interpretation --
    overall_score_raw = match_assessment.get("overall_score", 0)
    try:
        score_5 = round(float(overall_score_raw) / 20.0, 2)  # 0-100 → 0-5
    except (ValueError, TypeError):
        score_5 = 0.0
    score_info = interpret_score(score_5)

    # -- Gap analysis --
    gaps_raw = match_assessment.get("gaps") or []
    gaps: list[MatchGap] = []
    for gap in gaps_raw:
        if isinstance(gap, dict):
            desc = str(gap.get("description") or gap.get("title") or "")
            gaps.append(classify_gap(desc))
        elif isinstance(gap, str):
            gaps.append(classify_gap(gap))

    # -- Level strategy --
    archetype_label = str(archetype_detection_raw.get("primary") or "")
    job_posting = dict(
        dict(state.get("job_snapshot") or {}).get("job_posting") or {}
    )
    jd_level = str(job_posting.get("seniority") or job_posting.get("level") or "")
    if not jd_level:
        # Infer from archetype + role title
        query_profile = dict(state.get("query_profile") or {})
        jd_level = str(query_profile.get("job_level") or "")

    natural_level = str(candidate_profile.get("level") or "Senior/Staff")
    level_strategy = build_level_strategy(jd_level, natural_level)

    # -- Build enhanced evaluation --
    strengths = match_assessment.get("strengths") or []
    risks = match_assessment.get("risks") or []
    recommendation = match_assessment.get("recommendation") or "neutral"

    evaluation: dict[str, Any] = {
        "company": str(
            dict(state.get("query_profile") or {}).get("company") or ""
        ),
        "role": str(
            dict(state.get("query_profile") or {}).get("role") or ""
        ),
        "archetype": archetype_label,
        "overall_score": score_5,
        "score_tier": score_info["tier"],
        "recommendation": score_info["recommendation"],
        "draft_answers": score_info["draft_answers"],
        "should_apply": score_info["apply"],
        "match_recommendation": recommendation,
        "legitimacy_tier": str(
            legitimacy_raw.get("tier") or "Proceed with Caution"
        ),
        "strength_count": len(strengths),
        "gap_count": len(gaps),
        "risk_count": len(risks),
        "framing_hint": str(
            dict(state.get("adaptive_framing") or {}).get("headline") or ""
        )[:200],
        "level_strategy": level_strategy,
    }

    return {
        "offer_evaluation": evaluation,
        "gap_analysis": [g.model_dump() for g in gaps],
        "level_strategy": level_strategy,
        "score_interpretation": score_info,
    }
