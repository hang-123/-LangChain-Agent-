"""LegitimacyScorer — ghost job detection (Block G from career-ops).

Multi-signal weighted assessment of whether a posting represents a
real, active opening. Does NOT affect the 1-5 global score.

Signal reliability tiers (from career-ops _shared.md):
  High:   posting_age, apply_button
  Medium: tech_specificity, requirements_realism, layoff_news, repost_pattern
  Low:    salary_transparency, role_company_fit
"""

from __future__ import annotations

import re
from typing import Any

from api.core.contracts import (
    LegitimacyAssessment,
    LegitimacySignal,
    LegitimacyTier,
)

# -- Expired posting patterns (from liveness-core.mjs) --

HARD_EXPIRED_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"job (is )?no longer available",
        r"job.*no longer open",
        r"position has been filled",
        r"this job has expired",
        r"job posting has expired",
        r"no longer accepting applications",
        r"this (position|role|job) (is )?no longer",
        r"this job (listing )?is closed",
        r"job (listing )?not found",
        r"the page you are looking for doesn.?t exist",
        r"applications?\s+(?:(?:have|are|is)\s+)?closed",
        r"closed on \d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
        r"diese stelle (ist )?(nicht mehr|bereits) besetzt",
        r"offre (expirée|n'est plus disponible)",
    ]
]

# -- Tech terms for specificity scoring --

TECH_TERMS: set[str] = {
    "python", "java", "go", "rust", "typescript", "javascript", "c++", "scala",
    "react", "angular", "vue", "node.js", "django", "flask", "fastapi",
    "kubernetes", "docker", "terraform", "aws", "gcp", "azure",
    "postgres", "mysql", "mongodb", "redis", "kafka", "rabbitmq",
    "tensorflow", "pytorch", "jax", "mlflow", "kubeflow",
    "langchain", "llamaindex", "graphql", "rest", "grpc",
    "prometheus", "grafana", "datadog", "pagerduty",
    "spark", "flink", "airflow", "dbt", "snowflake", "bigquery",
    "git", "ci/cd", "jenkins", "github actions", "argo",
    "openai", "anthropic", "gemini", "llama", "mistral",
}


def _compute_tech_specificity(text: str) -> float:
    """Ratio of recognized tech terms to total words. 0.0-1.0."""
    words = text.lower().split()
    if not words:
        return 0.0
    tech_hits = sum(1 for w in words if w in TECH_TERMS)
    # Also match multi-word terms
    lower = text.lower()
    for term in TECH_TERMS:
        if " " in term and term in lower:
            tech_hits += 1
    return min(1.0, tech_hits / max(len(words), 1))


def _check_requirements_realism(text: str) -> tuple[float, list[str]]:
    """Check for unrealistic requirements (e.g., X years in tech that is Y years old).

    Returns (realism_score, list_of_warnings).
    """
    warnings: list[str] = []
    # Known tech ages (approximate years since public release)
    TECH_AGES: dict[str, int] = {
        "react": 13, "kubernetes": 11, "docker": 12, "typescript": 13,
        "rust": 10, "graphql": 10, "flutter": 7, "swiftui": 6,
        "langchain": 3, "llamaindex": 2, "openai api": 5,
    }
    # Pattern: "X+ years of Y"
    years_pattern = re.compile(r"(\d+)\+?\s*years?\s+(?:of\s+)?(?:experience\s+(?:in|with)\s+)?(\w[\w\s./#-]+?)(?:\.|,|\band\b|$)", re.IGNORECASE)
    for match in years_pattern.finditer(text):
        years = int(match.group(1))
        tech = match.group(2).strip().lower()
        for known_tech, age in TECH_AGES.items():
            if known_tech in tech and years > age:
                warnings.append(f"'{match.group(0).strip()}' — {known_tech} is only ~{age} years old")

    if not warnings:
        return 1.0, []
    severity = min(1.0, len(warnings) * 0.2)
    return max(0.2, 1.0 - severity), warnings


def _extract_layoff_signals(evidence_items: list[dict]) -> list[str]:
    """Scan evidence for layoff-related content."""
    signals: list[str] = []
    layoff_patterns = [
        re.compile(p, re.IGNORECASE)
        for p in [
            r"laid?\s*off\s*(\d+)", r"layoffs?\s*(?:of|affecting)?\s*(\d+)",
            r"reduc(?:ed?|ing)\s*(?:its)?\s*(?:workforce|headcount|staff)",
            r"hiring freeze", r"restructur(?:e|ing)",
        ]
    ]
    for evidence in evidence_items:
        snippet = str(evidence.get("snippet") or evidence.get("content") or "")
        for pat in layoff_patterns:
            m = pat.search(snippet)
            if m:
                signals.append(m.group(0)[:120])
                break
    return list(dict.fromkeys(signals))[:5]


def _check_expired_patterns(text: str) -> str | None:
    """Return the matched pattern source if text contains expired signals."""
    for pat in HARD_EXPIRED_PATTERNS:
        if pat.search(text):
            return pat.pattern
    return None


# -- Main node --


async def legitimacy_scorer_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: assess posting legitimacy (Block G).

    Reads: state["context"], state["evidence_items"], state["job_snapshot"],
           state["query_profile"].
    Writes: state["legitimacy_assessment"].
    """
    evidence_items = list(state.get("evidence_items") or [])
    context = list(state.get("context") or [])
    job_snapshot = dict(state.get("job_snapshot") or {})
    job_posting = dict(job_snapshot.get("job_posting") or {})

    # Combine all available text
    jd_text = str(job_posting.get("description") or job_posting.get("content") or "")
    all_text = " ".join([jd_text] + [c[:1000] for c in context[:5]])

    signals: list[LegitimacySignal] = []
    positive_count = 0
    concerning_count = 0

    # -- Signal 1: Expired patterns (High reliability) --
    expired_match = _check_expired_patterns(all_text)
    if expired_match:
        signals.append(LegitimacySignal(
            signal_name="expired_pattern",
            finding=f"Body matches expired posting pattern: {expired_match[:80]}",
            weight="Concerning",
            reliability="High",
        ))
        concerning_count += 1
    elif all_text.strip():
        signals.append(LegitimacySignal(
            signal_name="expired_pattern",
            finding="No expired posting patterns detected in body text.",
            weight="Neutral",
            reliability="High",
        ))

    # -- Signal 2: Tech specificity (Medium reliability) --
    specificity = _compute_tech_specificity(all_text)
    if specificity >= 0.08:
        signals.append(LegitimacySignal(
            signal_name="tech_specificity",
            finding=f"High technical specificity ({specificity:.2f}). JD names concrete tools and frameworks.",
            weight="Positive",
            reliability="Medium",
        ))
        positive_count += 1
    elif specificity >= 0.03:
        signals.append(LegitimacySignal(
            signal_name="tech_specificity",
            finding=f"Moderate technical specificity ({specificity:.2f}). Some concrete technologies mentioned.",
            weight="Neutral",
            reliability="Medium",
        ))
    else:
        signals.append(LegitimacySignal(
            signal_name="tech_specificity",
            finding=f"Low technical specificity ({specificity:.2f}). JD uses mostly generic language.",
            weight="Concerning",
            reliability="Medium",
        ))
        concerning_count += 1

    # -- Signal 3: Requirements realism (Medium reliability) --
    realism_score, realism_warnings = _check_requirements_realism(all_text)
    if realism_score >= 0.9:
        signals.append(LegitimacySignal(
            signal_name="requirements_realism",
            finding="No unrealistic experience requirements detected.",
            weight="Positive",
            reliability="Medium",
        ))
        positive_count += 1
    else:
        signals.append(LegitimacySignal(
            signal_name="requirements_realism",
            finding=f"Potentially unrealistic requirements: {'; '.join(realism_warnings[:3])}",
            weight="Concerning",
            reliability="Medium",
        ))
        concerning_count += 1

    # -- Signal 4: Layoff news (Medium reliability) --
    layoff_signals = _extract_layoff_signals(evidence_items)
    if layoff_signals:
        signals.append(LegitimacySignal(
            signal_name="layoff_news",
            finding=f"Layoff/hiring-freeze signals found in evidence: {'; '.join(layoff_signals[:3])}",
            weight="Concerning",
            reliability="Medium",
        ))
        concerning_count += 1
    else:
        signals.append(LegitimacySignal(
            signal_name="layoff_news",
            finding="No recent layoff or hiring freeze signals detected in evidence.",
            weight="Neutral",
            reliability="Medium",
        ))

    # -- Signal 5: Salary transparency (Low reliability) --
    salary_mentioned = bool(
        re.search(r"\$[\d,]+|salary|compensation.*range", all_text, re.IGNORECASE)
    )
    if salary_mentioned:
        signals.append(LegitimacySignal(
            signal_name="salary_transparency",
            finding="Salary or compensation range mentioned in posting.",
            weight="Positive",
            reliability="Low",
        ))
        positive_count += 1
    else:
        signals.append(LegitimacySignal(
            signal_name="salary_transparency",
            finding="No salary information in posting (jurisdiction-dependent, many legitimate reasons).",
            weight="Neutral",
            reliability="Low",
        ))

    # -- Signal 6: Content sufficiency --
    if len(all_text.strip()) < 300:
        signals.append(LegitimacySignal(
            signal_name="content_sufficiency",
            finding=f"Very little content ({len(all_text.strip())} chars) — likely nav/footer only.",
            weight="Concerning",
            reliability="High",
        ))
        concerning_count += 1
    else:
        signals.append(LegitimacySignal(
            signal_name="content_sufficiency",
            finding=f"Sufficient content ({len(all_text.strip())} chars).",
            weight="Positive",
            reliability="High",
        ))
        positive_count += 1

    # -- Determine tier --
    if concerning_count >= 3 or expired_match:
        tier = LegitimacyTier.SUSPICIOUS
        context_notes = "Multiple concerning signals. Investigate before investing time."
    elif concerning_count >= 1:
        tier = LegitimacyTier.PROCEED_CAUTION
        context_notes = "Mixed signals. Worth noting but not a blocker."
    else:
        tier = LegitimacyTier.HIGH_CONFIDENCE
        context_notes = "Most signals positive. Likely a real, active opening."

    # -- Context notes for edge cases --
    if not jd_text:
        context_notes += " Limited JD text available (batch mode or fetch failure)."

    return {
        "legitimacy_assessment": LegitimacyAssessment(
            tier=tier,
            tech_specificity_score=round(specificity, 3),
            requirements_realism_score=round(realism_score, 2),
            layoff_signals=layoff_signals,
            signals_table=signals,
            context_notes=context_notes,
            batch_mode=not bool(jd_text),
        ).model_dump(),
    }
