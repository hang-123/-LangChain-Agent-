"""ArchetypeDetector — classifies job postings into career-ops archetypes.

Algorithm (two-stage):
  1. Keyword matching: deterministic, fast, always runs.
  2. LLM confirmation: only triggered when confidence < 0.7.

Produces ArchetypeDetection + AdaptiveFraming for downstream nodes.
"""

from __future__ import annotations

from typing import Any

from api.core.contracts import (
    AdaptiveFraming,
    Archetype,
    ArchetypeDetection,
)

# -- Keyword definitions (from career-ops _shared.md) --

ARCHETYPE_KEYWORDS: dict[Archetype, list[str]] = {
    Archetype.LLMOPS: [
        "observability", "evals", "evaluation", "pipelines",
        "monitoring", "reliability", "production ai", "llm ops",
        "evaluation framework", "quality", "production ml",
    ],
    Archetype.AGENTIC: [
        "agent", "multi-agent", "hitl", "human in the loop",
        "orchestration", "workflow", "tool use", "function calling",
        "agent system", "autonomous", "agentic",
    ],
    Archetype.AI_PM: [
        "prd", "roadmap", "discovery", "stakeholder",
        "product manager", "backlog", "user stories",
        "product strategy", "go-to-market",
    ],
    Archetype.SOLUTIONS_ARCHITECT: [
        "architecture", "enterprise", "integration", "design",
        "systems", "technical strategy", "solution design",
        "system design", "distributed systems", "scalability",
    ],
    Archetype.FORWARD_DEPLOYED: [
        "client-facing", "deploy", "prototype", "fast delivery",
        "field", "customer success", "implementation",
        "proof of concept", "poc", "on-site delivery",
    ],
    Archetype.TRANSFORMATION: [
        "change management", "adoption", "enablement",
        "transformation", "digital transformation", "training",
        "organizational change", "culture change", "ai adoption",
    ],
}

# -- Adaptive framing profiles (from career-ops _profile.template.md) --

DEFAULT_FRAMING: dict[Archetype, AdaptiveFraming] = {
    Archetype.LLMOPS: AdaptiveFraming(
        archetype=Archetype.LLMOPS,
        headline="Production systems builder — observability, evals, closed-loop",
        emphasize=[
            "Production ML pipeline experience",
            "Observability and monitoring systems",
            "Evaluation framework design",
        ],
        de_emphasize=[
            "Pure research without production impact",
            "Single-model experimentation",
        ],
        proof_point_priority=["Production systems", "Evals & metrics", "Reliability"],
    ),
    Archetype.AGENTIC: AdaptiveFraming(
        archetype=Archetype.AGENTIC,
        headline="Multi-agent systems builder — orchestration, HITL, reliability",
        emphasize=[
            "Multi-agent orchestration",
            "Human-in-the-loop design",
            "Reliability and error handling",
        ],
        de_emphasize=["Single-bot automation", "Simple chatbot experience"],
        proof_point_priority=["Orchestration", "HITL systems", "Error handling"],
    ),
    Archetype.AI_PM: AdaptiveFraming(
        archetype=Archetype.AI_PM,
        headline="Technical builder who reduces uncertainty with prototypes, "
        "then productionizes with discipline",
        emphasize=[
            "Product discovery through prototyping",
            "PRD authoring with technical depth",
            "Metric-driven iteration",
        ],
        de_emphasize=["Pure project management", "Non-technical coordination"],
        proof_point_priority=["Product discovery", "PRDs & metrics", "Delivery"],
    ),
    Archetype.SOLUTIONS_ARCHITECT: AdaptiveFraming(
        archetype=Archetype.SOLUTIONS_ARCHITECT,
        headline="System designer with real integration experience",
        emphasize=[
            "End-to-end architecture design",
            "Enterprise integration patterns",
            "Make vs buy decision-making",
        ],
        de_emphasize=["Single-service optimization", "Theoretical architecture"],
        proof_point_priority=["System design", "Integrations", "Enterprise context"],
    ),
    Archetype.FORWARD_DEPLOYED: AdaptiveFraming(
        archetype=Archetype.FORWARD_DEPLOYED,
        headline="Builder who ships fast with observability from day one",
        emphasize=[
            "Rapid prototyping and delivery",
            "Client-facing communication",
            "Production-grade observability",
        ],
        de_emphasize=["Long-term roadmap planning", "Pure R&D work"],
        proof_point_priority=["Fast delivery", "Client impact", "Production"],
    ),
    Archetype.TRANSFORMATION: AdaptiveFraming(
        archetype=Archetype.TRANSFORMATION,
        headline="Change agent who leads AI adoption with measurable outcomes",
        emphasize=[
            "Organizational change management",
            "AI adoption and enablement",
            "Measurable transformation outcomes",
        ],
        de_emphasize=["Individual contributor execution", "Tactical task management"],
        proof_point_priority=["Change management", "Adoption metrics", "Team enablement"],
    ),
}


# -- Deterministic keyword matcher --


def _match_archetypes_keywords(text: str) -> dict[Archetype, float]:
    """Score each archetype by keyword match ratio. Returns {archetype: score}."""
    lower = text.lower()
    scores: dict[Archetype, float] = {}
    for archetype, keywords in ARCHETYPE_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lower)
        scores[archetype] = hits / len(keywords) if keywords else 0.0
    return scores


def _detect_from_keywords(text: str) -> ArchetypeDetection:
    """Deterministic archetype detection from keyword scores."""
    scores = _match_archetypes_keywords(text)
    sorted_arches = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary, primary_score = sorted_arches[0]
    secondary, secondary_score = sorted_arches[1] if len(sorted_arches) > 1 else (None, 0.0)

    # Confidence = ratio of primary to secondary score (normalized)
    gap = primary_score - secondary_score
    confidence = min(1.0, 0.5 + gap * 2.0) if primary_score > 0 else 0.3

    keyword_matches = [
        kw for kw in ARCHETYPE_KEYWORDS[primary]
        if kw in text.lower()
    ]

    return ArchetypeDetection(
        primary=primary,
        secondary=secondary if secondary_score > 0.1 else None,
        confidence=round(confidence, 2),
        keyword_matches=keyword_matches[:10],
        reasoning=f"Keyword match: primary={primary.value}({primary_score:.2f}), "
        f"secondary={secondary.value if secondary else 'none'}({secondary_score:.2f})",
    )


# -- LLM-based confirmer (for low confidence) --


async def _llm_confirm_archetype(text: str, initial: ArchetypeDetection) -> ArchetypeDetection:
    """Use LLM to confirm or refine archetype when keyword confidence is low."""
    from api.core.llm import invoke_structured_output
    from pydantic import BaseModel, Field

    class LLMArchetypeResult(BaseModel):
        primary: str = Field(description="Primary archetype")
        secondary: str | None = Field(default=None, description="Secondary archetype if hybrid")
        reasoning: str = Field(description="One sentence explaining the classification")

    archetype_options = "\n".join(f"- {a.value}: {', '.join(ARCHETYPE_KEYWORDS[a][:4])}" for a in Archetype)
    prompt = (
        "Classify this job posting into one of these archetypes (or hybrid of two):\n\n"
        f"{archetype_options}\n\n"
        f"Initial keyword detection: {initial.primary.value} (confidence: {initial.confidence})\n\n"
        "Job Description:\n{text}\n\n"
        "Respond with the most appropriate archetype classification."
    )

    try:
        result = await invoke_structured_output(
            LLMArchetypeResult,
            system=prompt,
            human=text[:6000],
        )
        if result:
            try:
                new_primary = Archetype(result.primary)
            except ValueError:
                new_primary = initial.primary
            new_secondary = None
            if result.secondary:
                try:
                    new_secondary = Archetype(result.secondary)
                except ValueError:
                    pass
            return ArchetypeDetection(
                primary=new_primary,
                secondary=new_secondary,
                confidence=0.7,  # LLM confirmed, but not perfect
                keyword_matches=initial.keyword_matches,
                reasoning=result.reasoning or initial.reasoning,
            )
    except Exception:
        pass
    return initial


# -- Main node --


async def archetype_detector_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: detect archetype from JD text and job snapshot.

    Reads state["query"], state["job_snapshot"], state["context"].
    Writes state["archetype_detection"], state["adaptive_framing"].
    """
    # Collect text sources
    texts: list[str] = [str(state.get("query") or "")]
    job_snapshot = dict(state.get("job_snapshot") or {})
    job_posting = dict(job_snapshot.get("job_posting") or {})
    jd_text = str(job_posting.get("description") or job_posting.get("content") or "")
    if jd_text:
        texts.append(jd_text)

    # Also scan context (evidence snippets from SearchAgent)
    context = list(state.get("context") or [])
    combined = " ".join(texts + [c[:500] for c in context[:5]])

    if len(combined.strip()) < 50:
        return {
            "archetype_detection": ArchetypeDetection(
                primary=Archetype.LLMOPS,
                confidence=0.0,
                reasoning="Insufficient text for classification",
            ).model_dump(),
            "adaptive_framing": DEFAULT_FRAMING[Archetype.LLMOPS].model_dump(),
        }

    detection = _detect_from_keywords(combined)

    # LLM confirmation for low confidence
    if detection.confidence < 0.7 and jd_text:
        detection = await _llm_confirm_archetype(combined, detection)

    framing = DEFAULT_FRAMING.get(detection.primary, DEFAULT_FRAMING[Archetype.LLMOPS])

    return {
        "archetype_detection": detection.model_dump(),
        "adaptive_framing": framing.model_dump(),
    }
