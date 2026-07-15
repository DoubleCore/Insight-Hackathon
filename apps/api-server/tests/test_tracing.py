from __future__ import annotations


def test_tracing_span_is_noop_when_not_enabled() -> None:
    from app.services.tracing import safe_hash, start_span

    with start_span("test.noop", {"payload": {"count": 1}}) as span:
        assert span.trace_id is None
        span.set_attribute("status", "completed")
        span.set_attributes({"candidate_count": 3})

    assert safe_hash("NVIDIA") == safe_hash("NVIDIA")
    assert safe_hash("NVIDIA") != safe_hash("TSMC")
