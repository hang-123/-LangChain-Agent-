from __future__ import annotations

from typing import Any


def unique_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        clean = item.strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def parse_context_item(item: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in item.splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        parsed[key.strip().upper()] = value.strip()
    return parsed


def parse_context_items(context: list[str]) -> list[dict[str, str]]:
    return [parse_context_item(item) for item in context if item and item.strip()]


def source_text(parsed: dict[str, str]) -> str:
    return " ".join(
        [
            parsed.get("QUERY", ""),
            parsed.get("TITLE", ""),
            parsed.get("SNIPPET", ""),
            parsed.get("URL", ""),
            parsed.get("RELEVANCE_HINT", ""),
        ]
    ).strip()


def source_ref(parsed: dict[str, str]) -> str:
    title = parsed.get("TITLE", "无标题")
    url = parsed.get("URL", "")
    source_class = parsed.get("SOURCE_CLASS", parsed.get("TYPE", "unknown"))
    return f"[{source_class}] {title} | {url}".strip()


def source_matches_tokens(parsed: dict[str, str], tokens: list[str]) -> bool:
    haystack = source_text(parsed).lower()
    return any(token.strip() and token.lower() in haystack for token in tokens)


def source_matches_company(parsed: dict[str, str], company: str) -> bool:
    if not company or company == "目标公司":
        return False
    return company.lower() in source_text(parsed).lower()


def source_class(parsed: dict[str, str]) -> str:
    return parsed.get("SOURCE_CLASS", parsed.get("TYPE", "unknown")).strip() or "unknown"


def evidence_source_class(item: dict[str, Any]) -> str:
    return str(item.get("source_class") or item.get("raw_type") or item.get("SOURCE_CLASS") or "unknown").strip() or "unknown"


def evidence_ref(item: dict[str, Any]) -> str:
    title = str(item.get("title") or item.get("TITLE") or "无标题").strip()
    url = str(item.get("url") or item.get("URL") or "").strip()
    source_class = evidence_source_class(item)
    source_id = str(item.get("source_id") or "").strip()
    prefix = f"{source_id} " if source_id else ""
    return f"{prefix}[{source_class}] {title} | {url}".strip()


def evidence_text(item: dict[str, Any]) -> str:
    return " ".join(
        [
            str(item.get("query") or item.get("QUERY") or ""),
            str(item.get("title") or item.get("TITLE") or ""),
            str(item.get("snippet") or item.get("SNIPPET") or ""),
            str(item.get("url") or item.get("URL") or ""),
            str(item.get("relevance_hint") or item.get("RELEVANCE_HINT") or ""),
        ]
    ).strip()


def evidence_matches_tokens(item: dict[str, Any], tokens: list[str]) -> bool:
    haystack = evidence_text(item).lower()
    return any(token.strip() and token.lower() in haystack for token in tokens)


def evidence_matches_company(item: dict[str, Any], company: str) -> bool:
    if not company or company == "目标公司":
        return False
    return company.lower() in evidence_text(item).lower()


def clip_text(text: str, limit: int = 80) -> str:
    clean = " ".join(text.split()).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def context_item_to_evidence(parsed: dict[str, str], index: int) -> dict[str, Any]:
    published = parsed.get("PUBLISHED", "未知")
    fresh_score = 25
    if any(token in published for token in ["2026", "2025"]):
        fresh_score = 85
    elif "2024" in published:
        fresh_score = 65
    return {
        "source_id": parsed.get("SOURCE_ID", f"source-{index}"),
        "source_class": source_class(parsed),
        "query": parsed.get("QUERY", ""),
        "url": parsed.get("URL", ""),
        "title": parsed.get("TITLE", "无标题"),
        "snippet": parsed.get("SNIPPET", ""),
        "published": published,
        "relevance_hint": parsed.get("RELEVANCE_HINT", ""),
        "company_specific": False,
        "freshness_score": fresh_score,
        "quality_score": 50,
    }


def coerce_evidence_items(raw_items: Any, context: list[str] | None = None) -> list[dict[str, Any]]:
    evidence_items: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for index, raw_item in enumerate(raw_items, start=1):
            if not isinstance(raw_item, dict):
                continue
            evidence_items.append(
                {
                    "source_id": str(raw_item.get("source_id") or f"source-{index}"),
                    "source_class": evidence_source_class(raw_item),
                    "query": str(raw_item.get("query") or ""),
                    "url": str(raw_item.get("url") or ""),
                    "title": str(raw_item.get("title") or "无标题"),
                    "snippet": str(raw_item.get("snippet") or ""),
                    "published": str(raw_item.get("published") or "未知"),
                    "relevance_hint": str(raw_item.get("relevance_hint") or ""),
                    "company_specific": bool(raw_item.get("company_specific")),
                    "freshness_score": int(raw_item.get("freshness_score") or 0),
                    "quality_score": int(raw_item.get("quality_score") or 0),
                }
            )
    if evidence_items:
        return evidence_items
    parsed_items = parse_context_items(context or [])
    return [context_item_to_evidence(parsed, index) for index, parsed in enumerate(parsed_items, start=1)]


def collect_source_refs(
    parsed_items: list[dict[str, str]],
    *,
    source_classes: list[str] | None = None,
    limit: int = 3,
) -> list[str]:
    selected: list[str] = []
    for parsed in parsed_items:
        if source_classes is not None and source_class(parsed) not in source_classes:
            continue
        selected.append(source_ref(parsed))
        if len(selected) >= limit:
            break
    return selected


def collect_evidence_refs(
    evidence_items: list[dict[str, Any]],
    *,
    source_classes: list[str] | None = None,
    limit: int = 3,
    company_specific_only: bool = False,
) -> list[str]:
    selected: list[str] = []
    for item in evidence_items:
        if source_classes is not None and evidence_source_class(item) not in source_classes:
            continue
        if company_specific_only and not bool(item.get("company_specific")):
            continue
        selected.append(evidence_ref(item))
        if len(selected) >= limit:
            break
    return selected


def evidence_map_for_classes(
    parsed_items: list[dict[str, str]],
    *,
    mapping: dict[str, list[str]],
    limit: int = 3,
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for key, source_classes in mapping.items():
        refs = collect_source_refs(parsed_items, source_classes=source_classes, limit=limit)
        if refs:
            result[key] = refs
    return result


def flatten_fallback_flags(flags: dict[str, Any]) -> dict[str, bool]:
    return {
        "fallback_query": bool(flags.get("query")),
        "fallback_insight": bool(flags.get("insight")),
        "fallback_report": bool(flags.get("report")),
    }
