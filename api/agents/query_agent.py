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
from api.core.prompts import Claim, QueryAgentResponse, SYSTEM_PROMPT_QUERY
from api.agents.job_intelligence_agent import job_intelligence_agent_node
from api.agents.matching_agent import matching_agent_node
from api.agents.resume_tailor_agent import build_resume_tailoring_artifacts


TECH_KEYWORDS = [
    "Python",
    "Java",
    "Go",
    "C++",
    "Rust",
    "SQL",
    "MySQL",
    "PostgreSQL",
    "Redis",
    "Kafka",
    "RocketMQ",
    "RabbitMQ",
    "Flink",
    "Spark",
    "Hive",
    "Hadoop",
    "ClickHouse",
    "Elasticsearch",
    "Linux",
    "Docker",
    "Kubernetes",
    "K8s",
    "Prometheus",
    "Grafana",
    "Spring",
    "Spring Boot",
    "JVM",
    "gRPC",
    "HTTP",
    "RPC",
    "微服务",
    "分布式",
    "系统设计",
    "高并发",
    "稳定性",
    "可观测性",
    "数据仓库",
    "数据平台",
]


def _keyword_matches(text: str, keyword: str) -> bool:
    haystack = str(text or "")
    needle = str(keyword or "").strip()
    if not haystack or not needle:
        return False
    if any(char.isalnum() for char in needle):
        pattern = r"(?<![A-Za-z0-9+])" + re.escape(needle) + r"(?![A-Za-z0-9+])"
        return re.search(pattern, haystack, flags=re.IGNORECASE) is not None
    return needle in haystack


def _truncate_context(context: list[str]) -> str:
    return "\n\n".join(context)[:14000]


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
    return [token for token in unique_strings(tokens) if token and token not in {"目标公司", "目标岗位"}]


def _is_company_specific(item: dict[str, Any], profile: dict[str, Any]) -> bool:
    if bool(item.get("company_specific")):
        return True
    company = str(profile.get("company") or "")
    tokens = _profile_tokens(profile)
    return evidence_matches_company(item, company) or evidence_matches_tokens(item, tokens)


def _extract_salary_signals(evidence_items: list[dict[str, Any]]) -> list[str]:
    text = _classes_text(evidence_items, ["salary_culture", "jd", "interview"])
    matches = re.findall(r"\d+\s*(?:k|K|w|W|万)\s*[-~至到]+\s*\d+\s*(?:k|K|w|W|万)", text)
    singles = re.findall(r"\d+\s*(?:k|K|w|W|万)", text)
    return unique_strings(matches + singles[:4])[:5]


def _collect_tech_keywords(evidence_items: list[dict[str, Any]]) -> list[str]:
    text = _classes_text(evidence_items, ["jd", "interview", "tech_stack"]).lower()
    found = [keyword for keyword in TECH_KEYWORDS if _keyword_matches(text, keyword)]
    return unique_strings(found)[:10]


def _derive_company_signals(
    evidence_items: list[dict[str, Any]],
    existing_signals: list[str],
    profile: dict[str, Any],
) -> list[str]:
    signals = list(existing_signals)
    for item in evidence_items:
        if evidence_source_class(item) != "company_profile":
            continue
        if not _is_company_specific(item, profile):
            continue
        snippet = clip_text(str(item.get("snippet") or item.get("title") or evidence_text(item)), 90)
        if snippet:
            signals.append(snippet)
    return unique_strings(signals)[:4]


def _derive_role_signals(evidence_items: list[dict[str, Any]], existing_signals: list[str]) -> list[str]:
    signals = list(existing_signals)
    for item in evidence_items:
        if evidence_source_class(item) != "jd":
            continue
        snippet = clip_text(str(item.get("snippet") or item.get("title") or evidence_text(item)), 90)
        if snippet:
            signals.append(snippet)
    return unique_strings(signals)[:4]


def _derive_company_specific_requirements(
    evidence_items: list[dict[str, Any]],
    profile: dict[str, Any],
) -> list[str]:
    company = str(profile.get("company") or "目标公司")
    requirements: list[str] = []
    for item in evidence_items:
        if not _is_company_specific(item, profile):
            continue
        detail = clip_text(str(item.get("snippet") or item.get("title") or evidence_text(item)), 92)
        if not detail:
            continue
        cls = evidence_source_class(item)
        if cls == "company_profile":
            requirements.append(f"{company} 的公司画像线索指向“{detail}”，准备时要把项目背景对齐到这个业务/组织语境。")
        elif cls == "jd":
            requirements.append(f"JD 证据明确强调“{detail}”，这更像该团队的硬要求，而不只是普通同类岗位的共性。")
        elif cls == "interview":
            requirements.append(f"面经证据显示该公司会围绕“{detail}”继续追问，需要提前准备真实项目细节。")
        elif cls == "salary_culture":
            requirements.append(f"薪资/文化讨论反复提到“{detail}”，说明匹配度不只看技术，也看节奏和协作预期。")
    if not requirements:
        requirements.append("公司特异性证据不足：当前还不能稳健判断这个团队与普通同类岗位的差异，建议补充公司画像、团队 JD 与定向面经。")
    return unique_strings(requirements)[:5]


def _derive_common_requirements(
    evidence_items: list[dict[str, Any]],
    tech_stack: list[str],
    intent: str,
) -> list[str]:
    requirements: list[str] = []
    if tech_stack:
        requirements.append(f"通用硬要求仍集中在 {', '.join(tech_stack[:4])} 等工程落地能力，而不是只会讲概念。")
    interview_text = _classes_text(evidence_items, ["interview"]).lower()
    jd_text = _classes_text(evidence_items, ["jd"]).lower()
    if any(token in interview_text + jd_text for token in ["系统设计", "架构", "稳定性", "高并发"]):
        requirements.append("通用面试要求里仍然会看系统设计、稳定性治理和复杂问题拆解。")
    if any(token in interview_text + jd_text for token in ["项目", "业务", "负责", "优化"]):
        requirements.append("项目叙事必须能讲清背景、取舍、指标和复盘，否则很容易被追问击穿。")
    if intent == "salary_culture":
        requirements.append("除技术匹配外，还要准备好薪资预期、协作方式和工作节奏上的表达。")
    if intent == "tech_coding":
        requirements.append("编码质量、算法复杂度和系统设计表达会是高频基础门槛。")
    if not requirements:
        requirements.append("通用要求证据偏少：目前只能确认会考基础工程能力，仍需补充更多 JD / 面经。")
    return unique_strings(requirements)[:4]


def _derive_interview_expectations(
    evidence_items: list[dict[str, Any]],
    profile: dict[str, Any],
    intent: str,
    tech_stack: list[str],
) -> list[str]:
    expectations: list[str] = []
    company = str(profile.get("company") or "目标公司")
    role = str(profile.get("role") or "目标岗位")
    interview_items = [item for item in evidence_items if evidence_source_class(item) == "interview"]
    for item in interview_items[:3]:
        detail = clip_text(str(item.get("snippet") or item.get("title") or evidence_text(item)), 88)
        if detail:
            expectations.append(f"真实面经显示，{company} {role} 会围绕“{detail}”继续深挖，不接受空泛回答。")
    if tech_stack:
        expectations.append(f"面试官通常会要求你把 {', '.join(tech_stack[:3])} 放进真实项目语境里讲清取舍和指标。")
    if intent == "tech_coding":
        expectations.append("技术向面试会更强调算法、编码质量、系统设计和故障定位。")
    if intent == "salary_culture":
        expectations.append("除技术题外，还要解释你和团队节奏、协作方式、薪资预期的匹配度。")
    if not expectations:
        expectations.append("面试官期待画像仍偏弱：当前证据不足以判断这家公司会如何追问，建议补更多定向面经。")
    return unique_strings(expectations)[:5]


def _derive_core_points(
    company_specific_requirements: list[str],
    common_requirements: list[str],
    interview_expectations: list[str],
    tech_stack: list[str],
    intent: str,
) -> list[str]:
    points: list[str] = []
    if company_specific_requirements:
        points.append("是否能把项目经历直接映射到该公司当前团队的真实业务场景和职责。")
    if tech_stack:
        points.append(f"是否对 {', '.join(tech_stack[:3])} 具备可落地、可量化、可追问的真实经验。")
    if any("系统设计" in item or "稳定性" in item for item in common_requirements + interview_expectations):
        points.append("是否能把系统设计、稳定性治理与线上问题处理讲到具体机制和取舍。")
    if intent == "tech_coding":
        points.append("是否能在编码、复杂度分析和系统拆解上体现稳定的技术基本功。")
    if intent == "salary_culture":
        points.append("是否能同时证明技术匹配和团队文化、工作节奏、薪资预期的适配度。")
    if not points:
        points.append("当前证据不足，只能保守判断面试会关注岗位匹配度和项目真实性。")
    return unique_strings(points)[:5]


def _derive_coverage_gaps(
    evidence_items: list[dict[str, Any]],
    *,
    intent: str,
    company_specific_source_count: int,
    tech_stack: list[str],
) -> list[str]:
    classes = {evidence_source_class(item) for item in evidence_items}
    gaps: list[str] = []
    if "company_profile" not in classes:
        gaps.append("缺少公司画像证据：还不能稳健判断业务线、组织特征和技术文化。")
    if "jd" not in classes:
        gaps.append("缺少最新 JD / 招聘要求证据：岗位职责和任职资格判断不够稳。")
    if "interview" not in classes:
        gaps.append("缺少真实面经证据：高频问题和追问路径仍然不够明确。")
    if intent == "tech_coding" and "tech_stack" not in classes:
        gaps.append("缺少技术栈垂直证据：系统设计、算法或工程关键词还不够集中。")
    if intent == "salary_culture" and "salary_culture" not in classes:
        gaps.append("缺少薪资/文化证据：当前无法稳健判断 WLB、薪资带和团队节奏。")
    if company_specific_source_count < 2:
        gaps.append("公司特异性证据偏少：现有证据仍容易被泛经验贴稀释。")
    if not tech_stack:
        gaps.append("技术栈命中偏弱：需要更明确的 JD / 面经来支撑技术要求判断。")
    return unique_strings(gaps)[:6]


def _build_evidence_map(evidence_items: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        "company_signals": collect_evidence_refs(evidence_items, source_classes=["company_profile"], limit=3, company_specific_only=True),
        "role_signals": collect_evidence_refs(evidence_items, source_classes=["jd"], limit=3),
        "company_specific_requirements": collect_evidence_refs(
            evidence_items,
            source_classes=["company_profile", "jd", "interview", "salary_culture"],
            limit=4,
            company_specific_only=True,
        ),
        "common_requirements": collect_evidence_refs(evidence_items, source_classes=["jd", "interview"], limit=3),
        "technical_stack_requirements": collect_evidence_refs(
            evidence_items,
            source_classes=["jd", "interview", "tech_stack"],
            limit=4,
        ),
        "salary_signals": collect_evidence_refs(evidence_items, source_classes=["salary_culture", "jd"], limit=3),
        "interview_expectations": collect_evidence_refs(evidence_items, source_classes=["interview", "jd"], limit=4),
    }


def _build_claim(
    claim_id: str,
    claim_type: str,
    statement: str,
    evidence_refs: list[str],
    *,
    confidence: int,
    company_specific: bool,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        claim_type=claim_type,  # type: ignore[arg-type]
        statement=statement,
        evidence_refs=unique_strings(evidence_refs)[:3],
        confidence=max(0, min(100, confidence)),
        company_specific=company_specific,
    )


def _build_claims(
    *,
    company_signals: list[str],
    role_signals: list[str],
    company_specific_requirements: list[str],
    common_requirements: list[str],
    technical_stack_requirements: list[str],
    salary_signals: list[str],
    interview_expectations: list[str],
    evidence_map: dict[str, list[str]],
    base_quality: int,
) -> list[Claim]:
    claims: list[Claim] = []

    def add_claims(items: list[str], claim_type: str, evidence_key: str, *, company_specific: bool, base_bonus: int) -> None:
        for index, statement in enumerate(items, start=1):
            if "证据不足" in statement and claim_type != "salary_signal":
                confidence = 38
            else:
                confidence = base_quality + base_bonus + (8 if company_specific else 0)
            claims.append(
                _build_claim(
                    claim_id=f"{claim_type}-{index}",
                    claim_type=claim_type,
                    statement=statement,
                    evidence_refs=evidence_map.get(evidence_key) or [],
                    confidence=confidence,
                    company_specific=company_specific,
                )
            )

    add_claims(company_signals[:2], "company_signal", "company_signals", company_specific=True, base_bonus=10)
    add_claims(role_signals[:2], "role_signal", "role_signals", company_specific=False, base_bonus=6)
    add_claims(
        company_specific_requirements[:3],
        "company_specific_requirement",
        "company_specific_requirements",
        company_specific=True,
        base_bonus=12,
    )
    add_claims(common_requirements[:3], "common_requirement", "common_requirements", company_specific=False, base_bonus=6)
    add_claims(
        technical_stack_requirements[:4],
        "technical_stack",
        "technical_stack_requirements",
        company_specific=False,
        base_bonus=8,
    )
    add_claims(salary_signals[:3], "salary_signal", "salary_signals", company_specific=False, base_bonus=5)
    add_claims(
        interview_expectations[:3],
        "interview_expectation",
        "interview_expectations",
        company_specific=False,
        base_bonus=7,
    )
    return claims[:16]


def _quality_metrics_for_claims(claims: list[Claim], context_quality_score: int) -> dict[str, Any]:
    claim_count = len(claims)
    with_evidence = sum(1 for claim in claims if claim.evidence_refs)
    company_specific_claim_count = sum(1 for claim in claims if claim.company_specific)
    technical_claim_count = sum(1 for claim in claims if claim.claim_type == "technical_stack")
    claim_evidence_coverage = int((with_evidence / claim_count) * 100) if claim_count else 0
    return {
        "claim_count": claim_count,
        "claim_with_evidence_count": with_evidence,
        "company_specific_claim_count": company_specific_claim_count,
        "technical_claim_count": technical_claim_count,
        "claim_evidence_coverage": claim_evidence_coverage,
        "context_quality_score": context_quality_score,
    }


def _root_cause_hint(coverage_gaps: list[str], quality_metrics: dict[str, Any]) -> str:
    if any("缺少" in gap or "证据偏少" in gap for gap in coverage_gaps):
        return "retrieval"
    if int(quality_metrics.get("claim_evidence_coverage") or 0) < 70:
        return "attribution"
    return "synthesis"


def _heuristic_query_response(
    *,
    company: str,
    role: str,
    intent: str,
    profile: dict[str, Any],
    context: list[str],
    insights: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> QueryAgentResponse:
    tech_stack = _collect_tech_keywords(evidence_items)
    company_signals = _derive_company_signals(
        evidence_items,
        [str(item) for item in insights.get("company_signals") or []],
        profile,
    )
    role_signals = _derive_role_signals(
        evidence_items,
        [str(item) for item in insights.get("role_signals") or []],
    )
    company_specific_requirements = _derive_company_specific_requirements(evidence_items, profile)
    common_requirements = _derive_common_requirements(evidence_items, tech_stack, intent)
    interview_expectations = _derive_interview_expectations(evidence_items, profile, intent, tech_stack)
    core_points = _derive_core_points(
        company_specific_requirements,
        common_requirements,
        interview_expectations,
        tech_stack,
        intent,
    )
    coverage_gaps = _derive_coverage_gaps(
        evidence_items,
        intent=intent,
        company_specific_source_count=int(insights.get("company_specific_source_count") or 0),
        tech_stack=tech_stack,
    )
    evidence_map = _build_evidence_map(evidence_items)
    context_quality_score = int(insights.get("context_quality_score") or 0)
    claims = _build_claims(
        company_signals=company_signals,
        role_signals=role_signals,
        company_specific_requirements=company_specific_requirements,
        common_requirements=common_requirements,
        technical_stack_requirements=tech_stack or ["技术栈证据偏弱：当前只能确认有服务端基础要求，仍需更强 JD / 面经支撑。"],
        salary_signals=_extract_salary_signals(evidence_items)
        or ["薪资证据不足：当前未拿到稳定的薪资带或待遇线索。"],
        interview_expectations=interview_expectations,
        evidence_map=evidence_map,
        base_quality=context_quality_score or 40,
    )
    quality_metrics = _quality_metrics_for_claims(claims, context_quality_score)

    if not evidence_items:
        coverage_gaps = unique_strings(
            ["context 缺失：QueryAgent 无法从真实检索结果中提炼公司差异和岗位要求。"] + coverage_gaps
        )

    return QueryAgentResponse(
        company=company,
        role=role,
        company_signals=company_signals,
        role_signals=role_signals,
        business_domain_hints=unique_strings(
            [str(profile.get("domain_hint") or "")]
            + [str(item) for item in insights.get("business_domain_hints") or []]
        )[:4],
        core_evaluation_points=core_points,
        company_specific_requirements=company_specific_requirements,
        common_requirements=common_requirements,
        technical_stack_requirements=tech_stack
        or ["技术栈证据偏弱：当前只能确认有服务端基础要求，仍需更强 JD / 面经支撑。"],
        salary_signals=_extract_salary_signals(evidence_items)
        or ["薪资证据不足：当前未拿到稳定的薪资带或待遇线索。"],
        interview_expectations=interview_expectations,
        claims=claims,
        evidence_map=evidence_map,
        quality_metrics=quality_metrics,
        context_quality_score=context_quality_score,
        coverage_gaps=coverage_gaps,
    )


def _fill_query_response_defaults(
    parsed: QueryAgentResponse,
    *,
    default: QueryAgentResponse,
    company: str,
    role: str,
    profile: dict[str, Any],
    insights: dict[str, Any],
) -> QueryAgentResponse:
    data = parsed.model_dump()
    defaults = default.model_dump()
    for key, fallback_value in defaults.items():
        current = data.get(key)
        if isinstance(fallback_value, list):
            data[key] = current or fallback_value
        elif isinstance(fallback_value, dict):
            merged = dict(fallback_value)
            merged.update(current or {})
            data[key] = merged
        elif fallback_value and not current:
            data[key] = fallback_value

    if not data.get("claims"):
        data["claims"] = defaults.get("claims") or []
    data["company"] = company
    data["role"] = role
    data["business_domain_hints"] = unique_strings(
        [str(profile.get("domain_hint") or "")]
        + [str(item) for item in data.get("business_domain_hints") or []]
        + [str(item) for item in insights.get("business_domain_hints") or []]
    )[:4]
    data["context_quality_score"] = max(
        int(data.get("context_quality_score") or 0),
        int(insights.get("context_quality_score") or 0),
    )
    return QueryAgentResponse.model_validate(data)


async def query_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    context = list(state.get("context") or [])
    query = str(state.get("query") or "").strip()
    intent = str(state.get("intent") or "general")
    insights = dict(state.get("insights") or {})
    profile = dict(state.get("query_profile") or {})
    evidence_items = coerce_evidence_items(state.get("evidence_items"), context)

    company = str(insights.get("company") or profile.get("company") or "目标公司")
    role = str(insights.get("role") or profile.get("role") or "目标岗位")

    heuristic = _heuristic_query_response(
        company=company,
        role=role,
        intent=intent,
        profile=profile,
        context=context,
        insights=insights,
        evidence_items=evidence_items,
    )

    fallback_used = False
    try:
        parsed = await invoke_structured_output(
            QueryAgentResponse,
            system_prompt=SYSTEM_PROMPT_QUERY,
            human_prompt=(
                "用户输入：\n{query}\n\n"
                "意图类型：{intent}\n\n"
                "query_profile：\n{query_profile}\n\n"
                "SearchAgent 已提取的上游画像：\n{upstream}\n\n"
                "结构化 evidence_items：\n{evidence_items}\n\n"
                "SearchAgent 写入的兼容展示层 context：\n{context}\n\n"
                "请严格基于证据输出结构化 JSON。先生成 claims，再聚合最终字段；若证据不足，直接写 coverage_gaps。"
            ),
            variables={
                "query": query,
                "intent": intent,
                "query_profile": profile,
                "upstream": {
                    "company": company,
                    "role": role,
                    "company_signals": insights.get("company_signals") or [],
                    "role_signals": insights.get("role_signals") or [],
                    "business_domain_hints": insights.get("business_domain_hints") or [],
                    "context_quality_score": insights.get("context_quality_score") or 0,
                    "retrieval_diagnostics": state.get("retrieval_diagnostics") or {},
                },
                "evidence_items": evidence_items[:8],
                "context": _truncate_context(context),
            },
            temperature=0.1,
        )
        parsed = _fill_query_response_defaults(
            parsed,
            default=heuristic,
            company=company,
            role=role,
            profile=profile,
            insights=insights,
        )
    except Exception:
        parsed = heuristic
        fallback_used = True

    quality_metrics = dict(parsed.quality_metrics or {})
    root_cause_hint = _root_cause_hint(parsed.coverage_gaps or [], quality_metrics)

    new_insights = insights.copy()
    fallback_flags = dict(new_insights.get("fallback_flags") or {})
    fallback_flags["query"] = fallback_used
    new_insights.update(parsed.model_dump())
    new_insights["evidence_items"] = evidence_items
    new_insights["quality_metrics"] = quality_metrics
    new_insights["root_cause_hint"] = root_cause_hint
    new_insights["fallback_flags"] = fallback_flags

    job_intelligence_update = await job_intelligence_agent_node(
        {
            "query_profile": profile,
            "evidence_items": evidence_items,
            "insights": new_insights,
            "raw_jd_text": state.get("raw_jd_text"),
            "context": context,
        }
    )
    matching_update = await matching_agent_node(
        {
            "candidate_profile": state.get("candidate_profile"),
            "resume_evidence": state.get("resume_evidence"),
            "job_snapshot": job_intelligence_update.get("job_snapshot"),
        }
    )
    tailoring_update = build_resume_tailoring_artifacts(
        candidate_profile=dict(state.get("candidate_profile") or {}),
        resume_evidence=list(state.get("resume_evidence") or []),
        job_snapshot=job_intelligence_update.get("job_snapshot") or {},
        match_assessment=matching_update.get("match_assessment") or {},
    )
    gap_text = "；".join((parsed.coverage_gaps or [])[:2]) if parsed.coverage_gaps else "证据覆盖较完整"
    result = {
        "insights": new_insights,
        "status": f"🧠 已完成 claim 归因与差异摘要提炼，当前缺口：{gap_text}。",
    }
    result.update(job_intelligence_update)
    result["match_assessment"] = matching_update.get("match_assessment") or {}
    result["tailor_plan"] = tailoring_update.get("tailor_plan") or {}
    result["resume_version"] = tailoring_update.get("resume_version") or {}
    result["fact_check_report"] = tailoring_update.get("fact_check_report") or {}
    if matching_update.get("status"):
        result["status"] = f"{result['status']} {str(matching_update['status'])}"
    if tailoring_update:
        result["status"] = f"{result['status']} ✍️ 已生成简历定制计划与事实校验结果。"
    return result
