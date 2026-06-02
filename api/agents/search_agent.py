# DEPRECATED (Phase 2): wrapped by api/tools/search_orchestrator.py.
# Core search logic still used via delegation. Do not add new routing logic here.
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Awaitable, Callable

from api.core.cache import get_redis_json_cache, get_sqlite_json_cache
from api.core.context_utils import clip_text, source_ref, unique_strings
from api.core.guardrails import enforce_tool_whitelist, filter_selected_sources
from api.core.job_query import build_query_profile
from api.core.metrics import observe_cache_lookup
from api.core.policy_loader import policy_from_state
from api.core.rag_store import search_rag_sources
from api.core.settings import get_settings
from api.tools import (
    NormalizedSource,
    ToolSearchResult,
    search_company_profile_sources,
    search_interview_sources,
    search_jd_sources,
    search_salary_culture_sources,
    search_tech_stack_sources,
)


SearchTaskFactory = Callable[[], Awaitable[ToolSearchResult]]

GENERIC_HINTS = ["面经", "牛客", "看准", "知乎", "经验贴", "八股"]
DOMAIN_HINTS = ["推荐", "广告", "风控", "电商", "数据平台", "基础架构", "搜索", "增长", "云平台"]
SEARCH_CACHE_NAMESPACE = "search_agent"


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        clean = item.strip()
        if not clean or clean.lower() in seen:
            continue
        seen.add(clean.lower())
        result.append(clean)
    return result


def _build_context_item(
    source: NormalizedSource,
    index: int,
    source_class: str,
    relevance_hint: str,
    company_specific: bool,
    freshness_score: int,
    quality_score: int,
) -> str:
    return (
        f"[SOURCE {index}]\n"
        f"SOURCE_ID: source-{index}\n"
        f"TYPE: {source.raw_type}\n"
        f"SOURCE_CLASS: {source_class}\n"
        f"QUERY: {source.query}\n"
        f"URL: {source.url}\n"
        f"TITLE: {source.title}\n"
        f"PUBLISHED: {source.published}\n"
        f"SCORE: {source.score}\n"
        f"RELEVANCE_HINT: {relevance_hint}\n"
        f"COMPANY_SPECIFIC: {str(company_specific).lower()}\n"
        f"FRESHNESS_SCORE: {freshness_score}\n"
        f"QUALITY_SCORE: {quality_score}\n"
        f"SNIPPET: {source.snippet}"
    )


def _select_search_tasks(profile: dict[str, Any], intent: str) -> list[tuple[str, SearchTaskFactory]]:
    company = str(profile.get("company") or "目标公司")
    role = str(profile.get("role") or "目标岗位")
    team_hint = str(profile.get("team_hint") or "")
    domain_hint = str(profile.get("domain_hint") or "")
    job_level = str(profile.get("job_level") or "")
    priority_topics = [str(item) for item in profile.get("priority_topics") or []]

    tasks: list[tuple[str, SearchTaskFactory]] = [
        (
            "company_profile_searcher",
            lambda: search_company_profile_sources(
                company=company,
                role=role,
                team_hint=team_hint,
                domain_hint=domain_hint,
            ),
        ),
        (
            "jd_searcher",
            lambda: search_jd_sources(
                company=company,
                role=role,
                team_hint=team_hint,
                domain_hint=domain_hint,
                job_level=job_level,
            ),
        ),
        (
            "interview_searcher",
            lambda: search_interview_sources(
                company=company,
                role=role,
                team_hint=team_hint,
                domain_hint=domain_hint,
                priority_topics=priority_topics,
            ),
        ),
    ]
    if intent == "tech_coding":
        tasks.append(
            (
                "tech_stack_searcher",
                lambda: search_tech_stack_sources(
                    company=company,
                    role=role,
                    team_hint=team_hint,
                    domain_hint=domain_hint,
                    priority_topics=priority_topics,
                ),
            )
        )
    if intent == "salary_culture":
        tasks.append(
            (
                "salary_culture_searcher",
                lambda: search_salary_culture_sources(
                    company=company,
                    role=role,
                    team_hint=team_hint,
                    job_level=job_level,
                ),
            )
        )
    return tasks


def _query_pack_for_tasks(task_specs: list[tuple[str, SearchTaskFactory]], profile: dict[str, Any], intent: str) -> list[dict[str, Any]]:
    company = str(profile.get("company") or "目标公司")
    role = str(profile.get("role") or "目标岗位")
    team_hint = str(profile.get("team_hint") or "")
    domain_hint = str(profile.get("domain_hint") or "")
    priority_topics = [str(item) for item in profile.get("priority_topics") or []]
    shared_tags = _unique([company, role, team_hint, domain_hint] + priority_topics)
    query_pack: list[dict[str, Any]] = []
    for tool_name, _ in task_specs:
        query_pack.append(
            {
                "tool_name": tool_name,
                "intent": intent,
                "target_company": company,
                "target_role": role,
                "focus_tags": shared_tags[:6],
            }
        )
    return query_pack


def _published_year_score(published: str) -> int:
    match = re.search(r"(20\d{2})", published)
    if not match:
        return 0
    year = int(match.group(1))
    if year >= 2026:
        return 3
    if year == 2025:
        return 2
    if year == 2024:
        return 1
    return 0


def _freshness_score(published: str) -> int:
    """Compute freshness score using spec 04 day-based decay.

    freshness_score = max(0, 100 - days_since_ingestion * 2)
    Falls back to year-based heuristic if published date cannot be parsed.
    """
    from datetime import datetime, timezone

    if published and published != "未知":
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m"):
            try:
                dt = datetime.strptime(published.strip()[:10], fmt)
                days = max(0, (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).days)
                return max(0, 100 - days * 2)
            except (ValueError, IndexError):
                continue

    # Fallback: year-based heuristic
    import re
    match = re.search(r"(20\d{2})", str(published))
    if match:
        year = int(match.group(1))
        current_year = datetime.now(timezone.utc).year
        if year == current_year:
            return 85
        if year == current_year - 1:
            return 65
        if year == current_year - 2:
            return 45
        return 25
    return 50  # Unknown date: neutral score


def _apply_freshness_decay(quality_score: float, freshness_score: int) -> tuple[float, bool]:
    """Apply freshness decay multiplier per spec 04 section 3.3.

    Returns (adjusted_score, may_be_stale).
    """
    if freshness_score >= 80:
        return quality_score, False
    if freshness_score >= 60:
        return quality_score * 0.85, False
    if freshness_score >= 40:
        return quality_score * 0.7, False
    return quality_score * 0.5, True


def _classify_source_tier(source: NormalizedSource, source_class: str, company_specific: bool) -> str:
    url = (source.url or "").lower()
    title = (source.title or "").lower()
    if source_class == "jd" and any(token in url for token in ["job", "career", "campus", "zhaopin", "recruit"]):
        return "official_jd"
    if source_class == "company_profile" and any(token in url for token in ["career", "about", "jobs", "blog", "tech"]):
        return "official_company"
    if source_class == "interview" and company_specific:
        return "high_quality_interview"
    if source_class == "interview" and any(token in title for token in ["面经", "一面", "二面", "三面"]):
        return "community_interview"
    return "generic"


def _classify_failure_reason(failure: str) -> str:
    lower = failure.lower()
    if any(token in lower for token in ["timeout", "timed out"]):
        return "timeout"
    if any(token in lower for token in ["401", "403", "429", "500", "503", "api", "missing:tavily_api_key"]):
        return "api_failure"
    if "无结果" in failure or "no result" in lower:
        return "no_result"
    if any(token in lower for token in ["generic", "泛", "经验贴"]):
        return "too_generic"
    return "runtime_failure"


def _classify_and_score_source(source: NormalizedSource, profile: dict[str, Any]) -> tuple[int, bool, str, str]:
    company = str(profile.get("company") or "")
    role = str(profile.get("role") or "")
    team_hint = str(profile.get("team_hint") or "")
    domain_hint = str(profile.get("domain_hint") or "")
    priority_topics = [str(item) for item in profile.get("priority_topics") or []]

    haystack = " ".join([source.title, source.snippet, source.url, source.query]).lower()
    reasons: list[str] = []
    score = 0

    if company and company.lower() in haystack:
        score += 5
        reasons.append("标题/摘要命中目标公司")
    if team_hint and team_hint.lower() in haystack:
        score += 4
        reasons.append("命中细分团队方向")
    if domain_hint and domain_hint.lower() in haystack:
        score += 3
        reasons.append("命中业务域线索")
    if role and role.lower() in haystack:
        score += 2
        reasons.append("命中岗位关键词")

    topic_hits = [topic for topic in priority_topics if topic and topic.lower() in haystack]
    if topic_hits:
        score += min(3, len(topic_hits))
        reasons.append(f"命中优先主题：{', '.join(topic_hits[:2])}")

    if source.raw_type in {"company_profile", "jd"}:
        score += 2
        reasons.append("属于高价值原始画像证据")

    if any(hint.lower() in haystack for hint in GENERIC_HINTS):
        score -= 2
        reasons.append("偏泛经验贴")

    if company and company.lower() in haystack and not (team_hint or domain_hint):
        score -= 1
        reasons.append("命中公司但缺少团队/业务域信息")

    year_score = _published_year_score(source.published)
    score += year_score
    if year_score > 0:
        reasons.append("发布时间较近")
    elif source.published in {"未知", ""}:
        score -= 1
        reasons.append("发布日期缺失")

    company_specific = company.lower() in haystack or bool(team_hint and team_hint.lower() in haystack) or bool(
        domain_hint and domain_hint.lower() in haystack
    )
    source_class = source.raw_type
    if not reasons:
        reasons.append("与岗位关键词基础相关")

    return score, company_specific, source_class, "；".join(reasons[:3])


def _summarize_signals(sources: list[NormalizedSource], *, limit: int = 3) -> list[str]:
    return _unique([clip_text(source.snippet, 72) for source in sources[:limit] if source.snippet])[:limit]


def _extract_domain_hints(sources: list[NormalizedSource], profile: dict[str, Any]) -> list[str]:
    haystack = " ".join([source.title + " " + source.snippet for source in sources]).lower()
    hints: list[str] = []
    if profile.get("domain_hint"):
        hints.append(str(profile["domain_hint"]))
    for marker in DOMAIN_HINTS:
        if marker.lower() in haystack:
            hints.append(marker)
    return _unique(hints)[:4]


def _build_evidence_map(
    selected: list[tuple[NormalizedSource, str, str, bool]],
) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for source, source_class, _, _ in selected:
        mapping.setdefault(source_class, []).append(
            source_ref({"SOURCE_CLASS": source_class, "TITLE": source.title, "URL": source.url})
        )
    return {key: unique_strings(value)[:3] for key, value in mapping.items()}


def _coverage_by_class(selected: list[tuple[NormalizedSource, str, str, bool]]) -> dict[str, int]:
    coverage: dict[str, int] = {}
    for _, source_class, _, _ in selected:
        coverage[source_class] = coverage.get(source_class, 0) + 1
    return coverage


def _select_sources(
    results: list[ToolSearchResult],
    *,
    profile: dict[str, Any],
    intent: str,
    context_limit: int = 12,
    generic_cap: int = 3,
    required_classes: list[str] | None = None,
) -> tuple[list[tuple[NormalizedSource, str, str, bool]], dict[str, Any]]:
    ranked: list[tuple[int, int, NormalizedSource, str, str, bool]] = []
    seen_urls: set[str] = set()
    source_urls: list[str] = []
    search_queries: list[str] = []
    search_failures: list[str] = []

    for result in results:
        search_queries.extend(result.search_queries)
        search_failures.extend(result.failures)
        is_rag = result.tool_name == "rag_vector_search"
        for source in result.sources:
            if not source.url or source.url in seen_urls:
                continue
            seen_urls.add(source.url)
            source_urls.append(source.url)
            score, company_specific, source_class, relevance_hint = _classify_and_score_source(source, profile)
            # RAG trust bonus: cached verified content is more trustworthy than first-time web scrapes
            if is_rag:
                rag_trust_bonus = float(get_settings().rag_trust_bonus or 0.5)
                score += rag_trust_bonus
            ranked.append((score, len(ranked), source, source_class, relevance_hint, company_specific))

    ranked.sort(key=lambda item: (item[0], item[2].published), reverse=True)

    selected: list[tuple[NormalizedSource, str, str, bool]] = []
    generic_count = 0
    company_specific_count = 0
    resolved_required_classes = list(required_classes or ["company_profile", "jd", "interview"])

    for required_class in resolved_required_classes:
        for _, _, source, source_class, relevance_hint, company_specific in ranked:
            if source_class != required_class:
                continue
            if any(existing_source.url == source.url for existing_source, _, _, _ in selected):
                continue
            selected.append((source, source_class, relevance_hint, company_specific))
            if company_specific:
                company_specific_count += 1
            else:
                generic_count += 1
            break

    for _, _, source, source_class, relevance_hint, company_specific in ranked:
        if len(selected) >= context_limit:
            break
        if any(existing_source.url == source.url for existing_source, _, _, _ in selected):
            continue
        if not company_specific and generic_count >= generic_cap:
            continue
        selected.append((source, source_class, relevance_hint, company_specific))
        if company_specific:
            company_specific_count += 1
        else:
            generic_count += 1

    coverage = _coverage_by_class(selected)
    missing_classes = [source_class for source_class in resolved_required_classes if coverage.get(source_class, 0) == 0]
    quality_score = min(100, company_specific_count * 12 + len(selected) * 5 - generic_count * 5 - len(missing_classes) * 8)
    company_specific_ratio = round(company_specific_count / len(selected), 2) if selected else 0.0
    generic_source_ratio = round(generic_count / len(selected), 2) if selected else 0.0
    return selected, {
        "source_urls": source_urls,
        "search_queries": unique_strings(search_queries),
        "search_failures": search_failures[:12],
        "evidence_count": len(selected),
        "company_specific_source_count": company_specific_count,
        "generic_source_count": generic_count,
        "context_quality_score": max(0, quality_score),
        "coverage_by_class": coverage,
        "missing_classes": missing_classes,
        "company_specific_ratio": company_specific_ratio,
        "generic_source_ratio": generic_source_ratio,
    }


def _build_evidence_item(
    source: NormalizedSource,
    index: int,
    source_class: str,
    relevance_hint: str,
    company_specific: bool,
) -> dict[str, Any]:
    freshness_score = _freshness_score(source.published)
    base_score = 55 + freshness_score // 4 + (10 if company_specific else 0) + (8 if source_class in {"company_profile", "jd"} else 0)
    quality_score = max(25, min(100, base_score))

    # Apply freshness decay per spec 04 section 3.3
    quality_score, may_be_stale = _apply_freshness_decay(quality_score, freshness_score)

    source_id = f"rag-source-{index}" if source.query == "rag_vector_search" else f"source-{index}"
    return {
        "source_id": source_id,
        "source_class": source_class,
        "query": source.query,
        "url": source.url,
        "title": source.title,
        "snippet": source.snippet,
        "published": source.published,
        "relevance_hint": relevance_hint,
        "company_specific": company_specific,
        "freshness_score": freshness_score,
        "quality_score": quality_score,
        "may_be_stale": may_be_stale,
    }


def _rebuild_selection_summary(
    selected: list[tuple[NormalizedSource, str, str, bool]],
    *,
    search_queries: list[str],
    search_failures: list[str],
    required_classes: list[str],
) -> dict[str, Any]:
    coverage = _coverage_by_class(selected)
    company_specific_count = sum(1 for _, _, _, company_specific in selected if company_specific)
    generic_count = len(selected) - company_specific_count
    missing_classes = [source_class for source_class in required_classes if coverage.get(source_class, 0) == 0]
    quality_score = min(100, company_specific_count * 12 + len(selected) * 5 - generic_count * 5 - len(missing_classes) * 8)
    return {
        "source_urls": [source.url for source, _, _, _ in selected if source.url],
        "search_queries": unique_strings(search_queries),
        "search_failures": search_failures[:12],
        "evidence_count": len(selected),
        "company_specific_source_count": company_specific_count,
        "generic_source_count": generic_count,
        "context_quality_score": max(0, quality_score),
        "coverage_by_class": coverage,
        "missing_classes": missing_classes,
        "company_specific_ratio": round(company_specific_count / len(selected), 2) if selected else 0.0,
        "generic_source_ratio": round(generic_count / len(selected), 2) if selected else 0.0,
    }


def _cache_key(query: str, intent: str, profile: dict[str, Any]) -> str:
    return json.dumps({"query": query, "intent": intent, "profile": profile}, ensure_ascii=False, sort_keys=True)


def _cache_backends() -> list[tuple[str, Any]]:
    settings = get_settings()
    if not settings.enable_cache:
        return []

    backends: list[tuple[str, Any]] = []
    redis_url = str(settings.redis_url or "").strip()
    if redis_url:
        backends.append(("redis", get_redis_json_cache(redis_url)))
    backends.append(("sqlite", get_sqlite_json_cache(settings.cache_db_path)))
    return backends


def _get_cached_result(key: str, *, ttl_seconds: int) -> dict[str, Any] | None:
    backends = _cache_backends()
    if not backends or ttl_seconds <= 0:
        return None

    for backend_name, backend in backends:
        try:
            cached_payload = backend.get(SEARCH_CACHE_NAMESPACE, key)
        except Exception:
            observe_cache_lookup("SearchAgent", backend_name, hit=False)
            continue
        if cached_payload is None:
            observe_cache_lookup("SearchAgent", backend_name, hit=False)
            continue

        observe_cache_lookup("SearchAgent", backend_name, hit=True)
        retrieval = dict(cached_payload.get("retrieval_diagnostics") or {})
        retrieval["cached"] = True
        retrieval["cache_backend"] = backend_name
        cached_payload["retrieval_diagnostics"] = retrieval
        cached_payload["status"] = f"🔍 SearchAgent 命中 {backend_name} 缓存，已直接复用最近一轮高质量证据。"
        return cached_payload
    return None


def _set_cached_result(key: str, payload: dict[str, Any], *, ttl_seconds: int) -> None:
    backends = _cache_backends()
    if not backends or ttl_seconds <= 0:
        return
    for backend_name, backend in backends:
        try:
            backend.set(SEARCH_CACHE_NAMESPACE, key, payload, ttl_seconds=ttl_seconds)
        except Exception:
            observe_cache_lookup("SearchAgent", backend_name, hit=False)


async def search_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    query = str(state.get("query") or "").strip()
    if not query:
        raise ValueError("query is empty")

    run_id = str(state.get("run_id") or "")
    intent = str(state.get("intent") or "general")
    policy = policy_from_state(state)
    retrieval_policy = policy.retrieval_policy
    profile = dict(state.get("query_profile") or {})
    if not profile:
        profile = build_query_profile(query, intent=intent)

    cache_key = _cache_key(query, intent, profile)
    task_specs = _select_search_tasks(profile, intent)
    task_specs, security_events = enforce_tool_whitelist(run_id, task_specs)
    query_pack = _query_pack_for_tasks(task_specs, profile, intent)

    cached_result = _get_cached_result(cache_key, ttl_seconds=retrieval_policy.cache_ttl_seconds)
    if cached_result is not None:
        cached_result["query_pack"] = list(cached_result.get("query_pack") or query_pack)
        retrieval = dict(cached_result.get("retrieval_diagnostics") or {})
        retrieval.setdefault("rag_enabled", bool(get_settings().enable_rag))
        retrieval.setdefault("rag_hit_count", 0)
        retrieval.setdefault("rag_failures", [])
        cached_result["retrieval_diagnostics"] = retrieval
        if security_events:
            cached_result["security_events"] = list(cached_result.get("security_events") or []) + [
                event.model_dump(mode="json") for event in security_events
            ]
        return cached_result

    gathered = await asyncio.gather(*(factory() for _, factory in task_specs), return_exceptions=True)

    tool_results: list[ToolSearchResult] = []
    execution_failures: list[str] = []
    used_tools: list[str] = []

    for (tool_name, _), result in zip(task_specs, gathered):
        used_tools.append(tool_name)
        if isinstance(result, Exception):
            execution_failures.append(f"{tool_name}:{result}")
            continue
        tool_results.append(result)

    rag_hits, rag_failures = [], []
    rag_enabled = bool(get_settings().enable_rag)
    if rag_enabled:
        try:
            rag_hits, rag_failures = await search_rag_sources(
                query=query,
                profile=profile,
                top_k=int(get_settings().rag_top_k or 4),
            )
        except Exception:
            rag_failures.append("rag:unexpected search failure")

    # Stage 2: LLM Reranker (fine-grained semantic scoring)
    if rag_hits and get_settings().enable_llm_reranker:
        try:
            from api.core.llm_reranker import build_llm_reranker
            reranker = build_llm_reranker()
            if reranker:
                rag_hits = await reranker.rerank_hits(
                    query=query, hits=rag_hits, top_k=max(5, len(rag_hits))
                )
        except Exception:
            pass  # LLM reranker failure is non-blocking

    if rag_hits:
        existing_urls = {source.url for result in tool_results for source in result.sources}
        rag_sources: list[NormalizedSource] = []
        for hit in rag_hits:
            if hit.chunk.url in existing_urls:
                continue
            rag_sources.append(
                NormalizedSource(
                    query="rag_vector_search",
                    url=hit.chunk.url,
                    title=hit.chunk.title,
                    snippet=hit.chunk.text,
                    published="未知",
                    score=str(hit.score),
                    raw_type=hit.chunk.source_type,
                )
            )
        if rag_sources:
            tool_results.append(
                ToolSearchResult(
                    tool_name="rag_vector_search",
                    search_queries=[query],
                    sources=rag_sources,
                )
            )
            used_tools.append("rag_vector_search")

    selected, merged = _select_sources(
        tool_results,
        profile=profile,
        intent=intent,
        context_limit=retrieval_policy.context_limit,
        generic_cap=retrieval_policy.generic_source_cap,
        required_classes=retrieval_policy.required_source_classes.get(intent),
    )
    selected, retrieval_events = filter_selected_sources(run_id, selected)
    required_classes = list(
        retrieval_policy.required_source_classes.get(intent)
        or ["company_profile", "jd", "interview"]
    )
    merged = _rebuild_selection_summary(
        selected,
        search_queries=list(merged["search_queries"]),
        search_failures=list(merged["search_failures"]),
        required_classes=required_classes,
    )
    security_events.extend(retrieval_events)
    merged["search_failures"] = merged["search_failures"] + execution_failures + rag_failures

    source_tier_counts: dict[str, int] = {}
    for source, source_class, _, company_specific in selected:
        tier = _classify_source_tier(source, source_class, company_specific)
        source_tier_counts[tier] = source_tier_counts.get(tier, 0) + 1

    failure_breakdown: dict[str, int] = {}
    for failure in merged["search_failures"]:
        key = _classify_failure_reason(str(failure))
        failure_breakdown[key] = failure_breakdown.get(key, 0) + 1

    evidence_items = [
        _build_evidence_item(source, index + 1, source_class, relevance_hint, company_specific)
        for index, (source, source_class, relevance_hint, company_specific) in enumerate(selected)
    ]
    context = [
        _build_context_item(
            source,
            index + 1,
            source_class,
            relevance_hint,
            company_specific,
            int(evidence_items[index]["freshness_score"]),
            int(evidence_items[index]["quality_score"]),
        )
        for index, (source, source_class, relevance_hint, company_specific) in enumerate(selected)
    ]

    sources_only = [source for source, _, _, _ in selected]
    company_sources = [source for source, source_class, _, _ in selected if source_class == "company_profile"]
    jd_sources = [source for source, source_class, _, _ in selected if source_class == "jd"]
    domain_hints = _extract_domain_hints(sources_only, profile)

    retrieval_diagnostics = {
        "coverage_by_class": merged["coverage_by_class"],
        "missing_classes": merged["missing_classes"],
        "company_specific_ratio": merged["company_specific_ratio"],
        "generic_source_ratio": merged["generic_source_ratio"],
        "failures": merged["search_failures"][:12],
        "failure_breakdown": failure_breakdown,
        "cached": False,
        "cache_backend": "redis" if get_settings().enable_cache and get_settings().redis_url else ("sqlite" if get_settings().enable_cache else "disabled"),
        "query_pack_size": len(merged["search_queries"]),
        "query_pack": query_pack,
        "source_tier_counts": source_tier_counts,
        "guardrail_blocked_sources": len(retrieval_events),
        "rag_enabled": rag_enabled,
        "rag_hit_count": len(rag_hits),
        "rag_failures": rag_failures[:6],
    }

    insights = dict(state.get("insights") or {})
    fallback_flags = dict(insights.get("fallback_flags") or {})
    quality_metrics = dict(insights.get("quality_metrics") or {})
    quality_metrics.update(
        {
            "evidence_count": merged["evidence_count"],
            "company_specific_source_count": merged["company_specific_source_count"],
            "context_quality_score": merged["context_quality_score"],
        }
    )
    insights.update(
        {
            "company": profile.get("company"),
            "role": profile.get("role"),
            "intent": intent,
            "used_tools": used_tools,
            "search_queries": merged["search_queries"],
            "source_urls": merged["source_urls"],
            "evidence_count": merged["evidence_count"],
            "search_failures": merged["search_failures"][:12],
            "company_signals": _summarize_signals(company_sources),
            "role_signals": _summarize_signals(jd_sources),
            "business_domain_hints": domain_hints,
            "evidence_map": _build_evidence_map(selected),
            "context_quality_score": merged["context_quality_score"],
            "company_specific_source_count": merged["company_specific_source_count"],
            "generic_source_count": merged["generic_source_count"],
            "quality_metrics": quality_metrics,
            "fallback_flags": {
                "query": bool(fallback_flags.get("query")),
                "insight": bool(fallback_flags.get("insight")),
                "report": bool(fallback_flags.get("report")),
            },
        }
    )

    result = {
        "query_profile": profile,
        "context": context,
        "evidence_items": evidence_items,
        "retrieval_diagnostics": retrieval_diagnostics,
        "query_pack": query_pack,
        "insights": insights,
        "status": (
            f"🔍 已按 intent={intent} 并发执行 {', '.join(used_tools)}，"
            f"保留 {merged['company_specific_source_count']} 条公司特异性证据，context 质量分 {merged['context_quality_score']}。"
            if context
            else f"🔍 已按 intent={intent} 执行并发检索，但未拿到可用证据；请检查 SearchAgent metadata。"
        ),
        "security_events": [event.model_dump(mode="json") for event in security_events],
    }
    _set_cached_result(cache_key, result, ttl_seconds=retrieval_policy.cache_ttl_seconds)
    return result
