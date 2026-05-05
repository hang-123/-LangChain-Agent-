from __future__ import annotations

from fastapi.testclient import TestClient

from api.core.metrics import observe_cache_lookup, observe_fallback, observe_llm_tokens, observe_node_latency
from api.core.settings import get_settings
from api.main import app


def test_metrics_endpoint_returns_prometheus_payload(monkeypatch):
    monkeypatch.setenv("ENABLE_NODE_PERF", "1")
    monkeypatch.setenv("ENABLE_CACHE", "1")
    get_settings.cache_clear()

    observe_node_latency("ReportAgent", 123)
    observe_llm_tokens("qwen-plus", token_in=12, token_out=34)
    observe_fallback("ReviewAgent", "ReportAgent")
    observe_cache_lookup("SearchAgent", "sqlite", hit=True)

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "agent_node_latency_ms" in response.text
    assert "agent_tokens_in_total" in response.text
    assert "agent_fallback_total" in response.text
    assert "agent_cache_hits_total" in response.text

    get_settings.cache_clear()
