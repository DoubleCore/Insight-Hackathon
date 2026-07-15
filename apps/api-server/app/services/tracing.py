from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from app.config import Settings


try:  # pragma: no cover - exercised when optional OTEL packages are installed.
    from opentelemetry import trace as _otel_trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import Status, StatusCode
except Exception:  # pragma: no cover - default local test env does not require OTEL.
    _otel_trace = None
    OTLPSpanExporter = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    Status = None
    StatusCode = None


_TRACER_NAME = 'dual_frontend.api'
_enabled = False


@dataclass(slots=True)
class TraceSpan:
    """Small adapter that keeps call sites independent from OTEL imports."""

    _span: Any | None = None
    trace_id: str | None = None

    def set_attribute(self, key: str, value: Any) -> None:
        if self._span is None:
            return
        coerced = _coerce_attribute(value)
        if coerced is None:
            return
        self._span.set_attribute(key, coerced)

    def set_attributes(self, attributes: Mapping[str, Any] | None) -> None:
        for key, value in (attributes or {}).items():
            self.set_attribute(key, value)

    def record_exception(self, exc: BaseException) -> None:
        if self._span is not None and hasattr(self._span, 'record_exception'):
            self._span.record_exception(exc)

    def set_error(self, message: str) -> None:
        if self._span is None or Status is None or StatusCode is None:
            return
        self._span.set_status(Status(StatusCode.ERROR, message))


def configure_tracing(settings: Settings) -> None:
    """Enable OpenTelemetry when configured; otherwise keep a no-op tracer.

    The API server must keep working in local/dev environments where optional
    OTEL packages or a collector are not installed.
    """

    global _enabled
    if _enabled:
        return
    should_enable = bool(settings.otel_enabled and _otel_trace and TracerProvider and Resource)
    if not should_enable:
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                'service.name': settings.otel_service_name,
                'deployment.environment': settings.app_env,
            }
        )
    )
    if settings.otel_exporter_otlp_endpoint and OTLPSpanExporter and BatchSpanProcessor:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    _otel_trace.set_tracer_provider(provider)
    _enabled = True


@contextmanager
def start_span(
    name: str, attributes: Mapping[str, Any] | None = None
) -> Iterator[TraceSpan]:
    if not _enabled or _otel_trace is None:
        yield TraceSpan()
        return

    tracer = _otel_trace.get_tracer(_TRACER_NAME)
    with tracer.start_as_current_span(name) as raw_span:
        span = TraceSpan(raw_span, trace_id=_trace_id(raw_span))
        span.set_attributes(attributes)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_error(f'{type(exc).__name__}: {exc}')
            raise


def safe_hash(value: str, *, length: int = 16) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:length]


def _trace_id(span: Any) -> str | None:
    context = span.get_span_context()
    if not getattr(context, 'is_valid', False):
        return None
    return f'{context.trace_id:032x}'


def _coerce_attribute(value: Any) -> str | bool | int | float | Sequence[str] | None:
    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if all(isinstance(item, str) for item in value):
            return list(value)
    return json.dumps(value, ensure_ascii=False, default=str, separators=(',', ':'))
