from __future__ import annotations

from typing import Any

from api.core.settings import get_settings

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
except Exception:  # pragma: no cover
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    Counter = None  # type: ignore[assignment]
    Histogram = None  # type: ignore[assignment]
    generate_latest = None  # type: ignore[assignment]


_NODE_LATENCY_MS = (
    Histogram(
        "agent_node_latency_ms",
        "Node latency in milliseconds.",
        labelnames=("node",),
        buckets=(10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, float("inf")),
    )
    if Histogram is not None
    else None
)
_TOKENS_IN_TOTAL = Counter(
    "agent_tokens_in_total",
    "Total prompt/input tokens by model.",
    labelnames=("model",),
) if Counter is not None else None
_TOKENS_OUT_TOTAL = Counter(
    "agent_tokens_out_total",
    "Total completion/output tokens by model.",
    labelnames=("model",),
) if Counter is not None else None
_FALLBACK_TOTAL = Counter(
    "agent_fallback_total",
    "Total fallback transitions triggered by ReviewAgent.",
    labelnames=("from_node", "to_node"),
) if Counter is not None else None
_CACHE_HITS_TOTAL = Counter(
    "agent_cache_hits_total",
    "Total cache hits by node and backend.",
    labelnames=("node", "backend"),
) if Counter is not None else None
_CACHE_MISSES_TOTAL = Counter(
    "agent_cache_misses_total",
    "Total cache misses by node and backend.",
    labelnames=("node", "backend"),
) if Counter is not None else None


def metrics_enabled() -> bool:
    settings = get_settings()
    return bool((settings.enable_node_perf or settings.enable_cache) and generate_latest is not None)


def observe_node_latency(node_name: str, duration_ms: int) -> None:
    if not metrics_enabled() or _NODE_LATENCY_MS is None:
        return
    _NODE_LATENCY_MS.labels(node=node_name).observe(max(0, duration_ms))


def observe_llm_tokens(model_name: str, *, token_in: int, token_out: int) -> None:
    if not metrics_enabled():
        return
    model = model_name or "unknown"
    if _TOKENS_IN_TOTAL is not None and token_in > 0:
        _TOKENS_IN_TOTAL.labels(model=model).inc(token_in)
    if _TOKENS_OUT_TOTAL is not None and token_out > 0:
        _TOKENS_OUT_TOTAL.labels(model=model).inc(token_out)


def observe_fallback(from_node: str, to_node: str) -> None:
    if not metrics_enabled() or _FALLBACK_TOTAL is None:
        return
    _FALLBACK_TOTAL.labels(from_node=from_node, to_node=to_node or "unknown").inc()


def observe_cache_lookup(node_name: str, backend_name: str, *, hit: bool) -> None:
    if not metrics_enabled():
        return
    counter = _CACHE_HITS_TOTAL if hit else _CACHE_MISSES_TOTAL
    if counter is None:
        return
    counter.labels(node=node_name, backend=backend_name or "unknown").inc()


def render_metrics_response() -> tuple[bytes, str] | None:
    if not metrics_enabled() or generate_latest is None:
        return None
    return generate_latest(), CONTENT_TYPE_LATEST
