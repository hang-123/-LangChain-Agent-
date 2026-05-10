"""AnalysisAgent — fully merged QueryAgent + InsightAgent.
Two-phase analysis: Job-side (requirements, signals, claims) + Candidate-side (risks, prep, action plan).
Independent implementation — no delegation to legacy agents."""

from __future__ import annotations

import re
from typing import Any

from api.core.context_utils import (
    clip_text,
    coerce_evidence_items,
    collect_evidence_refs,
    evidence_matches_company,
    evidence_matches_tokens,
    evidence_source_class,
    evidence_text,
    unique_strings,
)
from api.core.llm import invoke_structured_output
from api.core.prompts import (
    ActionPlanItem,
    Claim,
    QueryAgentResponse,
    InsightAgentResponse,
)
from api.core.prompt_loader import load_prompt

SYSTEM_PROMPT_ANALYSIS = load_prompt("analysis_system.txt")

TECH_KEYWORDS = [
    "Python", "Java", "Go", "C++", "Rust", "SQL", "MySQL", "PostgreSQL",
    "Redis", "Kafka", "RocketMQ", "RabbitMQ", "Flink", "Spark", "Hive",
    "Hadoop", "ClickHouse", "Elasticsearch", "Linux", "Docker", "Kubernetes",
    "K8s", "Prometheus", "Grafana", "Spring", "Spring Boot", "JVM",
    "gRPC", "HTTP", "RPC", "微服务", "分布式", "系统设计", "高并发",
    "稳定性", "可观测性", "数据仓库", "数据平台",
]


# ═══════════════ Phase 1: Job-side analysis helpers ═══════════════

def _keyword_matches(text: str, keyword: str) -> bool:
    haystack = str(text or "")
    needle = str(keyword or "").strip()
    if not haystack or not needle:
        return False
    if any(char.isalnum() for char in needle):
        pattern = r"(?<![A-Za-z0-9+])" + re.escape(needle) + r"(?![A-Za-z0-9+])"
        return re.search(pattern, haystack, flags=re.IGNORECASE) is not None
    return needle in haystack


def _classes_text(evidence_items: list[dict[str, Any]], classes: list[str] | None = None) -> str:
    chunks: list[str] = []
    for item in evidence_items:
        if classes is not None and evidence_source_class(item) not in classes:
            continue
        chunks.append(evidence_text(item))
    return "\n".join(chunks)


def _profile_tokens(profile: dict[str, Any]) -> list[str]:
    role = str(profile.get("role") or "")
    broad_roles = {"后端", "后端开发", "后端工程师", "开发", "平台", "数据", "目标岗位"}
    tokens = [
        str(profile.get("company") or ""),
        str(profile.get("team_hint") or ""),
        str(profile.get("domain_hint") or ""),
    ]
    if role and role not in broad_roles and len(role) >= 4:
        tokens.append(role)
    tokens.extend(str(item) for item in profile.get("priority_topics") or [])
    return [t for t in unique_strings(tokens) if t and t not in {"目标公司", "目标岗位"}]


def _is_company_specific(item: dict[str, Any], profile: dict[str, Any]) -> bool:
    if bool(item.get("company_specific")):
        return True
    company = str(profile.get("company") or "")
    tokens = _profile_tokens(profile)
    return evidence_matches_company(item, company) or evidence_matches_tokens(item, tokens)


def _collect_tech_keywords(evidence_items: list[dict[str, Any]]) -> list[str]:
    text = _classes_text(evidence_items, ["jd", "interview", "tech_stack"]).lower()
    return unique_strings([kw for kw in TECH_KEYWORDS if _keyword_matches(text, kw)])[:10]


def _extract_salary_signals(evidence_items: list[dict[str, Any]]) -> list[str]:
    text = _classes_text(evidence_items, ["salary_culture", "jd", "interview"])
    matches = re.findall(r"\d+\s*(?:k|K|w|W|万)\s*[-~至到]+\s*\d+\s*(?:k|K|w|W|万)", text)
    singles = re.findall(r"\d+\s*(?:k|K|w|W|万)", text)
    return unique_strings(matches + singles[:4])[:5]


# ═══════════════ Phase 2: Candidate-side helpers ═══════════════

def _claims_by_type(claims: list[Any], claim_type: str) -> list[Any]:
    return [c for c in claims if getattr(c, "claim_type", None) == claim_type]


def _claim_refs(claims: list[Any], *, company_specific_only: bool = False, limit: int = 3) -> list[str]:
    refs: list[str] = []
    for claim in claims:
        if company_specific_only and not getattr(claim, "company_specific", False):
            continue
        refs.extend(getattr(claim, "evidence_refs", []))
        if len(unique_strings(refs)) >= limit:
            break
    return unique_strings(refs)[:limit]


# ═══════════════ Heuristic fallback builders ═══════════════

def _heuristic_query_response(
    *, company: str, role: str, intent: str, profile: dict[str, Any],
    insights: dict[str, Any], evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build deterministic job-side analysis without LLM."""
    tech_stack = _collect_tech_keywords(evidence_items)
    company_specific_source_count = int(insights.get("company_specific_source_count") or 0)
    context_quality_score = int(insights.get("context_quality_score") or 0)

    return {
        "company": company, "role": role,
        "company_signals": unique_strings([str(s) for s in (insights.get("company_signals") or [])])[:4],
        "role_signals": unique_strings([str(s) for s in (insights.get("role_signals") or [])])[:4],
        "company_specific_requirements": [],
        "common_requirements": [],
        "technical_stack_requirements": tech_stack or ["技术栈证据偏弱"],
        "salary_signals": _extract_salary_signals(evidence_items) or ["薪资证据不足"],
        "interview_expectations": [],
        "coverage_gaps": [],
        "context_quality_score": context_quality_score,
        "claims": [],
        "evidence_map": {},
        "quality_metrics": {"claim_evidence_coverage": max(0, context_quality_score)},
    }


def _heuristic_insight_response(
    *, company: str, role: str, intent: str, insights: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build deterministic candidate-side analysis without LLM."""
    coverage_gaps = [str(item) for item in insights.get("coverage_gaps") or []]
    context_quality_score = int(insights.get("context_quality_score") or 0)
    company_specific_source_count = int(insights.get("company_specific_source_count") or 0)
    claim_evidence_coverage = int((insights.get("quality_metrics") or {}).get("claim_evidence_coverage") or 0)

    evidence_gap_summary: list[str] = []
    if context_quality_score < 45:
        evidence_gap_summary.append("context 质量分偏低，公司画像和岗位差异不够扎实。")
    if company_specific_source_count < 2:
        evidence_gap_summary.append("公司特异性证据偏少，报告应保守表达。")
    if claim_evidence_coverage < 70:
        evidence_gap_summary.append("claim 证据绑定覆盖率偏低。")

    return {
        "candidate_risks": [
            f"当前对 {company} {role} 的公司差异判断仍不稳。",
            "如果不能拿出更明确的 JD / 团队面经证据，很难证明理解了这个岗位的真实边界。",
        ],
        "interviewer_questions": [f"请结合真实项目，讲清你在 {role} 上的关键设计、优化和故障处理。"],
        "prep_strategy": ["先补公司画像、团队 JD 和定向面经，再继续做高置信度判断。",
                          "所有结论都必须标清证据来源；没有证据的地方明确写'暂不能判断'。"],
        "interview_angle": f"当前对 {company} {role} 的差异判断需保守处理：证据不足，建议先补证据再收紧结论。",
        "evidence_gap_summary": evidence_gap_summary,
        "action_plan_items": [],
        "action_plan_source_coverage": 0,
        "root_cause_hint": "retrieval" if evidence_gap_summary else "synthesis",
        "quality_metrics": {},
    }


# ═══════════════ Main Agent ═══════════════

async def run_analysis_agent(state: dict[str, Any]) -> dict[str, Any]:
    """AnalysisAgent — unified two-phase analysis.

    Phase 1: Job-side (company signals, role signals, requirements, tech stack, interview expectations)
    Phase 2: Candidate-side (risks, interviewer questions, prep strategy, action plan)

    Each phase tries LLM first, falls back to deterministic heuristic on failure.
    """
    query = str(state.get("query") or "").strip()
    intent = str(state.get("intent") or "general")
    insights = dict(state.get("insights") or {})
    profile = dict(state.get("query_profile") or {})
    evidence_items = coerce_evidence_items(state.get("evidence_items"), context)

    company = str(insights.get("company") or profile.get("company") or "")
    role = str(insights.get("role") or profile.get("role") or "")

    # Phase 2: read working_memory from upstream tools for enriched context
    new_context: list[str] = []
    working_memory = list(state.get("working_memory") or [])
    tool_context_parts: list[str] = []
    for entry in working_memory:
        source = entry.get("source", "")
        summary = entry.get("summary", {})
        if source == "search_orchestrator":
            tool_context_parts.append(
                f"[检索结果] 共{summary.get('evidence_count', 0)}条证据，"
                f"其中{summary.get('company_specific_count', 0)}条公司特异性证据"
            )
        elif source == "job_analyzer":
            tool_context_parts.append(
                f"[岗位分析] {summary.get('requirement_count', 0)}项要求，"
                f"原型={summary.get('archetype', '')}，"
                f"合法性={summary.get('legitimacy_tier', '')}"
            )
        elif source == "matching_engine":
            tool_context_parts.append(
                f"[匹配评估] 总分{summary.get('overall_score', 0)}，"
                f"{summary.get('strength_count', 0)}优势/{summary.get('gap_count', 0)}差距/{summary.get('risk_count', 0)}风险"
            )

    if tool_context_parts:
        tool_context_summary = "上游工具摘要：\n" + "\n".join(f"- {p}" for p in tool_context_parts)
        new_context.append(tool_context_summary)

    # ── Phase 1: Job-side analysis ──
    heuristic_q = _heuristic_query_response(
        company=company, role=role, intent=intent, profile=profile,
        insights=insights, evidence_items=evidence_items,
    )

    fallback_query = False
    try:
        parsed_q = await invoke_structured_output(
            QueryAgentResponse,
            system_prompt=SYSTEM_PROMPT_ANALYSIS,
            human_prompt=(
                "用户输入：{query}\n意图：{intent}\nquery_profile：{profile}\n"
                "evidence_items：{evidence}\n\n"
                "请执行 Phase 1 岗位侧分析，输出结构化 JSON（company_signals, role_signals, "
                "company_specific_requirements, common_requirements, technical_stack_requirements, "
                "salary_signals, interview_expectations, claims, coverage_gaps, context_quality_score）。"
            ),
            variables={
                "query": query, "intent": intent, "profile": profile,
                "evidence": str(evidence_items[:8]),
            },
            temperature=0.1,
        )
        q_result = parsed_q.model_dump()
    except Exception:
        q_result = heuristic_q
        fallback_query = True

    # ── Merge Phase 1 results into insights ──
    merged_insights = dict(insights)
    merged_insights.update(q_result)
    merged_insights["evidence_items"] = evidence_items if evidence_items else insights.get("evidence_items", [])

    # ── Phase 2: Candidate-side analysis ──
    heuristic_i = _heuristic_insight_response(
        company=company, role=role, intent=intent,
        insights=merged_insights, evidence_items=evidence_items,
    )

    fallback_insight = False
    try:
        parsed_i = await invoke_structured_output(
            InsightAgentResponse,
            system_prompt=SYSTEM_PROMPT_ANALYSIS,
            human_prompt=(
                "Phase 1 产出（结构化 claims 和信号）：{upstream}\n\n"
                "请执行 Phase 2 候选人侧分析，输出结构化 JSON（candidate_risks, interviewer_questions, "
                "interview_angle, prep_strategy, action_plan_items, evidence_gap_summary, "
                "action_plan_source_coverage）。\n"
                "每个 action_plan_item 必须包含 day, priority, goal, task, why_this_company, expected_outcome, evidence_refs。"
            ),
            variables={"upstream": str(merged_insights)},
            temperature=0.2,
        )
        i_result = parsed_i.model_dump()
    except Exception:
        i_result = heuristic_i
        fallback_insight = True

    # ── Merge all results ──
    merged_insights.update(i_result)
    merged_insights["quality_metrics"] = {
        "claim_evidence_coverage": max(0, int((q_result.get("quality_metrics") or {}).get("claim_evidence_coverage") or 0)),
        "action_plan_source_coverage": max(0, int(i_result.get("action_plan_source_coverage") or 0)),
    }
    fallback_flags = dict(merged_insights.get("fallback_flags") or {})
    fallback_flags["query"] = fallback_query
    fallback_flags["insight"] = fallback_insight
    merged_insights["fallback_flags"] = fallback_flags

    return {
        "context": new_context,
        "insights": merged_insights,
        "working_set_analysis": {
            "query_result": q_result,
            "insight_result": i_result,
            "quality_metrics": merged_insights["quality_metrics"],
        },
        "status": "AnalysisAgent 完成两阶段分析（岗位侧+候选人侧）。",
    }
