from __future__ import annotations

from api.agents.search_agent import _classify_failure_reason


def test_failure_reason_classification():
    assert _classify_failure_reason("missing:TAVILY_API_KEY") == "api_failure"
    assert _classify_failure_reason("timeout while requesting") == "timeout"
    assert _classify_failure_reason("generic 面经帖子过多") == "too_generic"
