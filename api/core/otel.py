from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from api.core.settings import get_settings

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
except Exception:  # pragma: no cover
    trace = None  # type: ignore[assignment]
    OTLPSpanExporter = None  # type: ignore[assignment]
    Resource = None  # type: ignore[assignment]
    TracerProvider = None  # type: ignore[assignment]
    BatchSpanProcessor = None  # type: ignore[assignment]
    ConsoleSpanExporter = None  # type: ignore[assignment]
    SimpleSpanProcessor = None  # type: ignore[assignment]


_INITIALIZED = False


def otel_available() -> bool:
    return trace is not None and TracerProvider is not None and Resource is not None


def otel_enabled() -> bool:
    return bool(get_settings().enable_otel and otel_available())


def initialize_otel() -> bool:
    global _INITIALIZED
    if _INITIALIZED or not otel_enabled():
        return otel_enabled()

    settings = get_settings()
    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    exporter_name = str(settings.otel_exporter or "console").strip().lower()

    if exporter_name == "otlp" and OTLPSpanExporter is not None and settings.otel_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    elif ConsoleSpanExporter is not None and SimpleSpanProcessor is not None:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _INITIALIZED = True
    return True


def get_tracer(name: str = "bettafish.harness") -> Any:
    if not initialize_otel() or trace is None:
        return None
    return trace.get_tracer(name)


@contextmanager
def start_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[Any | None]:
    tracer = get_tracer()
    if tracer is None:
        yield None
        return

    with tracer.start_as_current_span(name) as span:
        for key, value in (attributes or {}).items():
            if value is None:
                continue
            span.set_attribute(key, value)
        yield span

