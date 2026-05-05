from __future__ import annotations

from api.core.contracts import (
    ActionPlanItem,
    Claim,
    InsightAgentResponse,
    IntentRouterResponse,
    QueryAgentResponse,
    QueryProfile,
    ReviewAgentResponse,
    ReviewIssueDetail,
)
from api.core.prompt_loader import load_prompt

SYSTEM_PROMPT_INTENT_ROUTER = load_prompt("intent_router_system.txt")
SYSTEM_PROMPT_QUERY = load_prompt("query_system.txt")
SYSTEM_PROMPT_INSIGHT = load_prompt("insight_system.txt")
SYSTEM_PROMPT_REPORT = load_prompt("report_system.txt")
SYSTEM_PROMPT_REVIEW = load_prompt("review_system.txt")
