from __future__ import annotations

from typing import Any

from api.core.context_utils import coerce_evidence_items, collect_evidence_refs, unique_strings
from api.core.llm import invoke_structured_output
from api.core.prompts import ActionPlanItem, Claim, InsightAgentResponse, SYSTEM_PROMPT_INSIGHT


def _truncate_context(context: list[str]) -> str:
    return "\n\n".join(context)[:14000]


def _coerce_claims(raw_claims: Any) -> list[Claim]:
    claims: list[Claim] = []
    if not isinstance(raw_claims, list):
        return claims
    for raw_claim in raw_claims:
        try:
            claims.append(Claim.model_validate(raw_claim))
        except Exception:
            continue
    return claims


def _coerce_action_plan_items(raw_items: Any) -> list[ActionPlanItem]:
    items: list[ActionPlanItem] = []
    if not isinstance(raw_items, list):
        return items
    for raw_item in raw_items:
        try:
            items.append(ActionPlanItem.model_validate(raw_item))
        except Exception:
            continue
    items.sort(key=lambda item: item.day)
    return items


def _action_item(
    *,
    day: int,
    priority: str,
    goal: str,
    task: str,
    why_this_company: str,
    expected_outcome: str,
    evidence_refs: list[str],
) -> ActionPlanItem:
    return ActionPlanItem(
        day=day,
        priority=priority,  # type: ignore[arg-type]
        goal=goal,
        task=task,
        why_this_company=why_this_company,
        expected_outcome=expected_outcome,
        evidence_refs=unique_strings(evidence_refs)[:3],
    )


def _claims_by_type(claims: list[Claim], claim_type: str) -> list[Claim]:
    return [claim for claim in claims if claim.claim_type == claim_type]


def _claim_refs(claims: list[Claim], *, company_specific_only: bool = False, limit: int = 3) -> list[str]:
    refs: list[str] = []
    for claim in claims:
        if company_specific_only and not claim.company_specific:
            continue
        refs.extend(claim.evidence_refs)
        if len(unique_strings(refs)) >= limit:
            break
    return unique_strings(refs)[:limit]


def _build_evidence_gap_summary(
    *,
    coverage_gaps: list[str],
    context_quality_score: int,
    company_specific_source_count: int,
    claim_evidence_coverage: int,
) -> list[str]:
    gaps = list(coverage_gaps)
    if context_quality_score < 45:
        gaps.append("当前 context 质量分偏低，说明公司画像和岗位差异仍然不够扎实。")
    if company_specific_source_count < 2:
        gaps.append("公司特异性证据仍偏少，报告应保守表达，优先补公司画像、团队 JD 和定向面经。")
    if claim_evidence_coverage < 70:
        gaps.append("claim 的证据绑定覆盖率偏低，说明结论归因还不够稳。")
    return unique_strings(gaps)[:6]


def _build_candidate_risks(
    *,
    company: str,
    role: str,
    intent: str,
    company_specific_claims: list[Claim],
    technical_claims: list[Claim],
    interview_claims: list[Claim],
    evidence_gaps: list[str],
) -> list[str]:
    if evidence_gaps and len(company_specific_claims) <= 1:
        return unique_strings(
            [
                f"当前对 {company} {role} 的公司差异判断仍不稳，如果直接套用通用后端话术，很容易显得准备浅。",
                "如果不能拿出更明确的 JD / 团队面经证据，就很难证明自己理解了这个岗位的真实边界。",
                *evidence_gaps[:2],
            ]
        )[:4]

    risks: list[str] = []
    if company_specific_claims:
        risks.append(f"如果无法拿出能对应“{company_specific_claims[0].statement}”的真实项目证据，会被认为岗位映射能力不足。")
    if len(company_specific_claims) > 1:
        risks.append(f"如果只会讲通用经历，而讲不深“{company_specific_claims[1].statement}”，很容易在追问里失分。")
    if technical_claims:
        risks.append(f"如果不能把 {technical_claims[0].statement} 讲到具体机制、指标和取舍，技术深度会被快速识别为偏弱。")
    if interview_claims:
        risks.append(f"如果面对“{interview_claims[0].statement}”这类追问时只能讲概念，会被认为缺少真实项目落地经验。")
    if intent == "salary_culture":
        risks.append("如果薪资预期、协作方式和工作节奏边界表达含糊，会在匹配度环节失分。")
    if intent == "tech_coding":
        risks.append("如果编码、复杂度分析和系统设计表达不稳定，技术面会较快暴露短板。")
    return unique_strings(risks)[:5]


def _build_interviewer_questions(
    *,
    company: str,
    intent: str,
    company_specific_claims: list[Claim],
    technical_claims: list[Claim],
    interview_claims: list[Claim],
) -> list[str]:
    questions: list[str] = []
    if company_specific_claims:
        questions.append(f"你过去哪个项目最能证明自己能覆盖“{company_specific_claims[0].statement}”？具体做了什么、指标如何？")
    if technical_claims:
        questions.append(f"请结合真实项目，讲清你在 {technical_claims[0].statement} 上做过哪些关键设计、优化和故障处理。")
    if len(technical_claims) > 1:
        questions.append(f"如果 {technical_claims[1].statement} 相关链路线上抖动，你会如何定位、止损并验证修复效果？")
    if interview_claims:
        questions.append(f"{company} 的真实面经里经常会追问“{interview_claims[0].statement}”，你会如何把这个问题答深？")
    if intent == "tech_coding":
        questions.append("请现场写一个核心函数，解释复杂度、边界条件和为什么这样设计。")
    if intent == "salary_culture":
        questions.append("你希望的薪资区间、团队协作方式和工作节奏分别是什么，为什么和这个岗位匹配？")
    return unique_strings(questions)[:6]


def _build_conservative_action_plan(
    *,
    company: str,
    role: str,
    intent: str,
    evidence_gaps: list[str],
    company_refs: list[str],
    jd_refs: list[str],
    interview_refs: list[str],
) -> list[ActionPlanItem]:
    return [
        _action_item(
            day=1,
            priority="high",
            goal="补齐公司画像",
            task=f"围绕 {company} 的业务线、团队定位、招聘页面和公开技术文章补更多定向证据，先确认它到底是不是普通 {role}。"
            if company != "目标公司"
            else "先补齐明确的公司画像和团队背景证据，避免后续分析继续泛化。",
            why_this_company="当前最大问题不是准备动作不够多，而是公司特异性证据不够扎实，继续输出满配建议只会更模板化。",
            expected_outcome="一页公司画像卡片，包含业务域、团队方向、关键产品场景和高频关键词。",
            evidence_refs=company_refs or jd_refs,
        ),
        _action_item(
            day=2,
            priority="high",
            goal="补齐岗位硬要求",
            task=f"继续补最新 JD、任职资格和高频面经，把职责、技术栈和高频追问拆成表格，并标出哪些仍然证据不足。"
            if intent != "salary_culture"
            else "重点补薪资区间、团队文化、工作节奏和候选人口碑讨论，不要只看技术内容。",
            why_this_company=f"{company} 当前最缺的是可直接用于岗位归因的定向证据，而不是通用经验贴。",
            expected_outcome="岗位要求 / 证据出处 / 证据强度 三列表。",
            evidence_refs=jd_refs or interview_refs,
        ),
        _action_item(
            day=3,
            priority="high",
            goal="把简历映射到已有证据",
            task="只根据已经确认过的证据重写最相关的一段项目经历；仍然缺证据的地方明确写成“暂不能判断/待补证据”，不要硬凑。",
            why_this_company="证据不足时最容易犯的错误就是把通用后端经历硬套到任何公司身上，这一步是为了止住这种模板化。",
            expected_outcome="一版带证据标注的项目答题稿，以及一份待补证据清单。",
            evidence_refs=(company_refs + jd_refs + interview_refs)[:3],
        ),
    ]


def _build_action_plan_items(
    *,
    company: str,
    role: str,
    intent: str,
    company_specific_claims: list[Claim],
    technical_claims: list[Claim],
    interview_claims: list[Claim],
    salary_claims: list[Claim],
    candidate_risks: list[str],
    evidence_gaps: list[str],
    context_quality_score: int,
    company_specific_source_count: int,
) -> list[ActionPlanItem]:
    company_refs = _claim_refs(company_specific_claims, company_specific_only=True)
    tech_refs = _claim_refs(technical_claims)
    interview_refs = _claim_refs(interview_claims)
    salary_refs = _claim_refs(salary_claims)
    conservative = (
        context_quality_score < 45
        or company_specific_source_count < 2
        or len(company_specific_claims) < 2
        or len(evidence_gaps) >= 3
    )
    if conservative:
        return _build_conservative_action_plan(
            company=company,
            role=role,
            intent=intent,
            evidence_gaps=evidence_gaps,
            company_refs=company_refs,
            jd_refs=tech_refs,
            interview_refs=interview_refs,
        )

    domain_statement = company_specific_claims[0].statement if company_specific_claims else role
    return [
        _action_item(
            day=1,
            priority="high",
            goal="建立公司差异画像",
            task=f"把公司画像、JD 和面经里反复出现的业务线索整理成一页“{company} 为什么不是普通 {role}”的差异卡。",
            why_this_company=f"当前 claims 显示 {company} 的岗位重点靠近“{domain_statement}”，不先抽象出差异画像，后续准备会重新滑回通用模板。",
            expected_outcome="一页岗位差异卡，包含业务场景、关键职责、核心约束和你可映射的项目。",
            evidence_refs=company_refs,
        ),
        _action_item(
            day=2,
            priority="high",
            goal="补齐岗位核心技术栈",
            task=f"围绕 {', '.join(claim.statement for claim in technical_claims[:2]) or '岗位核心技术栈'} 重写最相关项目，补上架构图、取舍、指标和故障案例。",
            why_this_company="这些技术 claim 在真实 JD / 面经里反复出现，说明它们不是装饰词，而是会被继续深挖的硬要求。",
            expected_outcome="一版技术深挖答题稿，至少覆盖背景、方案、取舍、指标、复盘。",
            evidence_refs=tech_refs,
        ),
        _action_item(
            day=3,
            priority="high",
            goal="演练高风险追问",
            task=f"针对最危险的风险点做一次高压追问演练，重点修复“{candidate_risks[0]}”这一类会被连续追问的问题。",
            why_this_company="该岗位的面试更像证据核验，泛化表达会被快速击穿，必须先做高压场景演练。",
            expected_outcome="一组追问脚本和对应的答题卡，每题都带失败原因与修正版答案。",
            evidence_refs=interview_refs or tech_refs,
        ),
        _action_item(
            day=4,
            priority="medium",
            goal="准备业务/系统设计题",
            task=f"围绕 {company_specific_claims[0].statement} 设计一题系统题或业务题，讲清约束、容量、稳定性和取舍。",
            why_this_company=f"{company} 的公司特异性要求已经比较清晰，说明只会讲通用后端故事不够，需要把方案放回真实业务语境。",
            expected_outcome="一页系统设计答题稿，包含约束条件、关键组件、指标和监控告警。",
            evidence_refs=unique_strings(company_refs + tech_refs + interview_refs)[:3],
        ),
        _action_item(
            day=5,
            priority="medium",
            goal="做一次最终对齐",
            task=(
                "把薪资预期、团队节奏、协作方式与岗位要求做一次对齐，并准备反问问题。"
                if intent == "salary_culture"
                else "做一次 45 分钟模拟面试，验证公司差异画像、技术深挖和高压追问是否已经闭环。"
            ),
            why_this_company=(
                f"{company} 当前公开证据里已经出现了薪资/文化/工作节奏信号，最后一轮需要确认你是否真的接受。"
                if intent == "salary_culture"
                else "这是检查整套准备是否仍然依赖模板，而不是依据该公司真实证据来表达的最后关口。"
            ),
            expected_outcome="最终版自我介绍、项目稿、反问问题与缺口清单。",
            evidence_refs=(salary_refs or interview_refs or company_refs)[:3],
        ),
    ]


def _calculate_action_plan_source_coverage(items: list[ActionPlanItem]) -> int:
    if not items:
        return 0
    covered = sum(1 for item in items if item.evidence_refs)
    return int((covered / len(items)) * 100)


def _build_prep_strategy(
    *,
    company: str,
    role: str,
    intent: str,
    action_plan_items: list[ActionPlanItem],
    evidence_gaps: list[str],
) -> list[str]:
    if evidence_gaps:
        strategies = [
            "先补公司画像、团队 JD 和定向面经，再继续做高置信度的岗位匹配判断。",
            "所有结论都必须标清证据来源；没有证据的地方就明确写“暂不能判断”。",
            f"先把最相关的一段项目经历重写成面向 {company} {role} 的证据化版本，避免继续复用通用项目稿。",
        ]
        if intent == "salary_culture":
            strategies.append("额外补薪资区间、团队文化和工作节奏证据，再谈匹配度。")
        return unique_strings(strategies)[:5]

    strategies = [item.task for item in action_plan_items[:3]]
    strategies.append("每个回答都补上背景、约束、取舍、指标和复盘，避免只有结果没有过程。")
    if intent == "tech_coding":
        strategies.append("单独把系统设计与编码题练到能口头拆解边界条件、复杂度和优化路径。")
    if intent == "salary_culture":
        strategies.append("把薪资预期、协作方式和节奏边界提前表达成一版稳定说法。")
    return unique_strings(strategies)[:6]


def _heuristic_insight_response(
    *,
    company: str,
    role: str,
    intent: str,
    context: list[str],
    insights: dict[str, Any],
) -> InsightAgentResponse:
    evidence_items = coerce_evidence_items(insights.get("evidence_items"), context)
    claims = _coerce_claims(insights.get("claims") or [])
    if not claims:
        claims = _coerce_claims((insights.get("quality_metrics") or {}).get("claims"))
    coverage_gaps = [str(item) for item in insights.get("coverage_gaps") or []]
    context_quality_score = int(insights.get("context_quality_score") or 0)
    company_specific_source_count = int(insights.get("company_specific_source_count") or 0)
    claim_evidence_coverage = int((insights.get("quality_metrics") or {}).get("claim_evidence_coverage") or 0)

    if not evidence_items:
        evidence_items = coerce_evidence_items(None, context)

    if not claims:
        company_refs = collect_evidence_refs(evidence_items, source_classes=["company_profile", "jd"], limit=3)
        fallback_claims = [
            Claim(
                claim_id="fallback-company-1",
                claim_type="company_specific_requirement",
                statement=str((insights.get("company_specific_requirements") or ["公司特异性证据不足"])[0]),
                evidence_refs=company_refs,
                confidence=38,
                company_specific=True,
            )
        ]
        claims = fallback_claims

    company_specific_claims = _claims_by_type(claims, "company_specific_requirement")
    technical_claims = _claims_by_type(claims, "technical_stack")
    interview_claims = _claims_by_type(claims, "interview_expectation")
    salary_claims = _claims_by_type(claims, "salary_signal")

    evidence_gap_summary = _build_evidence_gap_summary(
        coverage_gaps=coverage_gaps,
        context_quality_score=context_quality_score,
        company_specific_source_count=company_specific_source_count,
        claim_evidence_coverage=claim_evidence_coverage,
    )
    candidate_risks = _build_candidate_risks(
        company=company,
        role=role,
        intent=intent,
        company_specific_claims=company_specific_claims,
        technical_claims=technical_claims,
        interview_claims=interview_claims,
        evidence_gaps=evidence_gap_summary,
    )
    interviewer_questions = _build_interviewer_questions(
        company=company,
        intent=intent,
        company_specific_claims=company_specific_claims,
        technical_claims=technical_claims,
        interview_claims=interview_claims,
    )
    action_plan_items = _build_action_plan_items(
        company=company,
        role=role,
        intent=intent,
        company_specific_claims=company_specific_claims,
        technical_claims=technical_claims,
        interview_claims=interview_claims,
        salary_claims=salary_claims,
        candidate_risks=candidate_risks,
        evidence_gaps=evidence_gap_summary,
        context_quality_score=context_quality_score,
        company_specific_source_count=company_specific_source_count,
    )
    action_plan_source_coverage = _calculate_action_plan_source_coverage(action_plan_items)
    prep_strategy = _build_prep_strategy(
        company=company,
        role=role,
        intent=intent,
        action_plan_items=action_plan_items,
        evidence_gaps=evidence_gap_summary,
    )

    if evidence_gap_summary:
        interview_angle = (
            f"当前对 {company} {role} 的差异判断仍需保守处理：已有一些真实证据，但公司特异性仍不够稳，"
            "更适合先补证据、再收紧结论和准备动作。"
        )
    else:
        interview_angle = (
            f"从面试官视角看，这个岗位并不接受通用模板回答；如果你能把项目经历映射到 {company} 当前岗位的"
            "真实业务场景、技术栈和追问路径，竞争力会明显提升。"
        )

    root_cause_hint = "retrieval" if evidence_gap_summary else "synthesis"
    if claim_evidence_coverage and claim_evidence_coverage < 70:
        root_cause_hint = "attribution"
    quality_metrics = dict(insights.get("quality_metrics") or {})
    quality_metrics.update(
        {
            "action_plan_source_coverage": action_plan_source_coverage,
            "candidate_risk_count": len(candidate_risks),
            "interviewer_question_count": len(interviewer_questions),
        }
    )

    return InsightAgentResponse(
        candidate_risks=candidate_risks,
        interviewer_questions=interviewer_questions,
        prep_strategy=prep_strategy,
        interview_angle=interview_angle,
        evidence_gap_summary=evidence_gap_summary,
        action_plan_items=action_plan_items,
        action_plan_source_coverage=action_plan_source_coverage,
        root_cause_hint=root_cause_hint,
        quality_metrics=quality_metrics,
    )


def _fill_insight_defaults(parsed: InsightAgentResponse, *, default: InsightAgentResponse) -> InsightAgentResponse:
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
        elif isinstance(fallback_value, int):
            data[key] = current or fallback_value
        elif fallback_value and not current:
            data[key] = fallback_value
    if not data.get("action_plan_items"):
        data["action_plan_items"] = defaults.get("action_plan_items") or []
    return InsightAgentResponse.model_validate(data)


async def insight_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    context = list(state.get("context") or [])
    query = str(state.get("query") or "").strip()
    intent = str(state.get("intent") or "general")
    insights = dict(state.get("insights") or {})
    profile = dict(state.get("query_profile") or {})
    evidence_items = coerce_evidence_items(state.get("evidence_items"), context)

    company = str(insights.get("company") or profile.get("company") or "目标公司")
    role = str(insights.get("role") or profile.get("role") or "目标岗位")

    heuristic = _heuristic_insight_response(
        company=company,
        role=role,
        intent=intent,
        context=context,
        insights=insights,
    )

    fallback_used = False
    try:
        parsed = await invoke_structured_output(
            InsightAgentResponse,
            system_prompt=SYSTEM_PROMPT_INSIGHT,
            human_prompt=(
                "用户目标：\n{query}\n\n"
                "意图类型：{intent}\n\n"
                "query_profile：\n{query_profile}\n\n"
                "QueryAgent 结构化结果：\n{upstream}\n\n"
                "SearchAgent 结构化 evidence_items：\n{evidence_items}\n\n"
                "SearchAgent 原始证据 context：\n{context}\n\n"
                "请严格基于 claims 和证据输出 JSON。证据不足时，优先给 evidence_gap_summary 和补证据行动，不要输出泛化模板建议。"
            ),
            variables={
                "query": query,
                "intent": intent,
                "query_profile": profile,
                "upstream": insights,
                "evidence_items": evidence_items[:8],
                "context": _truncate_context(context),
            },
            temperature=0.2,
        )
        parsed = _fill_insight_defaults(parsed, default=heuristic)
    except Exception:
        parsed = heuristic
        fallback_used = True

    new_insights = insights.copy()
    fallback_flags = dict(new_insights.get("fallback_flags") or {})
    fallback_flags["insight"] = fallback_used
    new_insights.update(parsed.model_dump())
    new_insights["evidence_items"] = evidence_items
    new_insights["quality_metrics"] = parsed.quality_metrics
    new_insights["root_cause_hint"] = parsed.root_cause_hint
    new_insights["fallback_flags"] = fallback_flags

    return {
        "insights": new_insights,
        "status": (
            "🎯 已完成风险诊断、追问设计和动态行动项生成。"
            if parsed.action_plan_items
            else "🎯 已完成风险诊断，但当前更建议先补证据。"
        ),
    }
