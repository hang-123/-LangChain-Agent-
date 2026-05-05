from __future__ import annotations

import re
from typing import Any


COMPANY_MARKERS = [
    "字节跳动",
    "字节",
    "阿里巴巴",
    "阿里云",
    "阿里",
    "腾讯",
    "小红书",
    "美团",
    "京东",
    "百度",
    "华为",
    "快手",
    "滴滴",
]

ROLE_MARKERS = [
    "推荐后端",
    "广告后端",
    "风控后端",
    "交易后端",
    "基础架构",
    "基础平台",
    "云平台工程",
    "数据平台后端",
    "后端开发",
    "后端工程师",
    "后端",
    "平台工程",
    "平台开发",
    "平台",
    "数据平台",
    "数据开发",
    "数据工程",
    "数据",
    "算法工程师",
    "算法",
    "测试开发",
    "测试",
    "客户端",
    "前端开发",
    "前端",
    "运维开发",
    "运维",
    "SRE",
    "开发",
]

DOMAIN_MARKERS: dict[str, list[str]] = {
    "推荐": ["推荐", "推荐系统", "feed", "内容分发"],
    "广告": ["广告", "商业化", "广告系统", "广告平台"],
    "风控": ["风控", "反作弊", "安全风控"],
    "电商": ["电商", "交易", "支付", "履约", "供应链"],
    "数据平台": ["数据平台", "数仓", "数据仓库", "数据链路", "批流"],
    "基础架构": ["基础架构", "infra", "平台工程", "云平台", "中间件"],
    "搜索": ["搜索", "检索", "搜索引擎"],
    "增长": ["增长", "拉新", "用户增长"],
}

PRIORITY_TOPIC_MARKERS: list[str] = [
    "系统设计",
    "算法",
    "编码",
    "性能优化",
    "高并发",
    "稳定性",
    "可观测性",
    "分布式",
    "缓存",
    "消息队列",
    "薪资",
    "文化",
    "WLB",
]


def normalize_query_text(text: str, *, limit: int = 320) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def extract_company_and_role(query: str) -> tuple[str, str]:
    text = normalize_query_text(query)
    company = "目标公司"
    role = "目标岗位"

    for marker in COMPANY_MARKERS:
        if marker in text:
            company = marker
            break

    for marker in ROLE_MARKERS:
        if marker in text:
            role = marker
            break

    return company, role


def infer_job_level(query: str) -> str:
    text = query.lower()
    if any(token in text for token in ["实习", "intern", "暑期"]):
        return "实习"
    if any(token in text for token in ["秋招", "春招", "校招", "应届"]):
        return "校招"
    return "社招/通用"


def infer_domain_hint(query: str) -> str:
    text = normalize_query_text(query)
    for domain, markers in DOMAIN_MARKERS.items():
        if any(marker in text for marker in markers):
            return domain
    return ""


def infer_team_hint(query: str, role: str, domain_hint: str) -> str:
    text = normalize_query_text(query)
    if domain_hint:
        return f"{domain_hint}{role}" if role not in domain_hint else domain_hint
    for marker in ROLE_MARKERS:
        if marker in text and marker not in {"开发", "后端", "平台", "数据"}:
            return marker
    return ""


def infer_priority_topics(query: str, *, intent: str, domain_hint: str = "", role: str = "") -> list[str]:
    text = normalize_query_text(query)
    topics: list[str] = []
    for marker in PRIORITY_TOPIC_MARKERS:
        if marker.lower() in text.lower():
            topics.append(marker)
    if domain_hint:
        topics.append(domain_hint)
    if role and role not in topics:
        topics.append(role)
    if intent == "tech_coding":
        topics.extend(["系统设计", "性能优化", "高并发"])
    if intent == "salary_culture":
        topics.extend(["薪资", "文化", "工作节奏"])
    return _unique_topics(topics)


def build_query_profile(query: str, *, intent: str) -> dict[str, Any]:
    company, role = extract_company_and_role(query)
    domain_hint = infer_domain_hint(query)
    team_hint = infer_team_hint(query, role, domain_hint)
    return {
        "company": company,
        "role": role,
        "team_hint": team_hint,
        "job_level": infer_job_level(query),
        "domain_hint": domain_hint,
        "priority_topics": infer_priority_topics(query, intent=intent, domain_hint=domain_hint, role=role),
    }


def _unique_topics(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        clean = item.strip()
        if not clean or clean.lower() in seen:
            continue
        seen.add(clean.lower())
        result.append(clean)
    return result[:6]
