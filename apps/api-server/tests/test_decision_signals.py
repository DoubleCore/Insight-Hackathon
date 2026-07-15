from __future__ import annotations

from pathlib import Path


def test_build_decision_signal_episode_body_contains_policy_context() -> None:
    from app.services.decision_signals import build_decision_signal_episode_body

    body = build_decision_signal_episode_body(
        title="摩尔定律放缓与先进封装",
        category="technology",
        source_type="text",
        content="摩尔定律放缓推动 Chiplet 和先进封装发展。",
        keywords="摩尔定律, Chiplet, 先进封装",
        industry_impact="封装测试、HBM、AI 服务器需求增强。",
        dc_implication="有助于解释 AI 基础设施业务机会。",
    )

    assert "资料类型：技术趋势" in body
    assert "标题：摩尔定律放缓与先进封装" in body
    assert "关键词：摩尔定律, Chiplet, 先进封装" in body
    assert "对神州数码业务判断的可能影响" in body


def test_extract_text_from_upload_rejects_unknown_file_type() -> None:
    from app.services.decision_signals import extract_text_from_upload

    try:
        extract_text_from_upload("report.docx", b"payload")
    except ValueError as exc:
        assert ".txt / .md / .pdf" in str(exc)
    else:
        raise AssertionError("unsupported file type should raise ValueError")


def test_import_decision_signal_registers_evidence_record(tmp_path: Path) -> None:
    import asyncio

    from app.config import Settings
    from app.services.decision_signals import import_decision_signal

    class FakeEpisode:
        uuid = "episode-1"

    class FakeResult:
        episode = FakeEpisode()

    class FakeGraphiti:
        def __init__(self) -> None:
            self.kwargs = {}

        async def add_episode(self, **kwargs):
            self.kwargs = kwargs
            return FakeResult()

        async def close(self):
            return None

    graphiti = FakeGraphiti()

    result = asyncio.run(
        import_decision_signal(
            settings=Settings(siliconflow_api_key="key"),
            graphiti_factory=lambda _settings: graphiti,
            group_id="semiconductor_dc_kg",
            title="华为与稻盛经营哲学",
            category="business_implication",
            source_type="text",
            content="公开资料显示，华为管理讨论中曾引用稻盛和夫经营哲学。",
            source_url="https://example.com/huawei-inamori",
            keywords="华为, 稻盛和夫, 经营哲学",
            evidence_dir=tmp_path,
        )
    )

    evidence_id = result["evidence_id"]
    assert evidence_id.startswith("DS-")
    assert f"证据ID：{evidence_id}" in graphiti.kwargs["episode_body"]
    evidence_file = tmp_path / "decision_signals.jsonl"
    assert evidence_file.exists()
    payload = evidence_file.read_text(encoding="utf-8")
    assert evidence_id in payload
    assert "华为与稻盛经营哲学" in payload


def test_import_decision_signal_falls_back_to_raw_episode(
    tmp_path: Path,
) -> None:
    import asyncio

    from app.config import Settings
    from app.services.decision_signals import import_decision_signal

    class FakeDriver:
        provider = "neo4j"
        graph_operations_interface = None

        def __init__(self) -> None:
            self.queries: list[tuple[str, dict[str, object]]] = []

        async def execute_query(self, query: str, **kwargs):
            self.queries.append((query, kwargs))
            if "MATCH (s:Saga)" in query and "WHERE s.group_id IN $group_ids" in query:
                return [], None, None
            if "HAS_EPISODE" in query and "RETURN e.uuid" in query:
                return [], None, None
            return [], None, None

    class FakeGraphiti:
        def __init__(self) -> None:
            self.driver = FakeDriver()
            self.closed = False

        async def add_episode(self, **_kwargs):
            raise ValueError("LLM schema error")

        async def close(self):
            self.closed = True

    graphiti = FakeGraphiti()

    result = asyncio.run(
        import_decision_signal(
            settings=Settings(siliconflow_api_key="key"),
            graphiti_factory=lambda _settings: graphiti,
            group_id="semiconductor_dc_kg",
            title="华为与稻盛经营哲学",
            category="business_implication",
            source_type="text",
            content="公开资料显示，华为管理讨论中曾引用稻盛和夫经营哲学。",
            evidence_dir=tmp_path,
        )
    )

    assert result["episode_uuid"]
    assert result["fallback_reason"] == "ValueError: LLM schema error"
    assert graphiti.closed is True
    assert any("MERGE (n:Episodic" in query for query, _ in graphiti.driver.queries)
    assert any("MERGE (n:Saga" in query for query, _ in graphiti.driver.queries)
    assert any("HAS_EPISODE" in query for query, _ in graphiti.driver.queries)
    evidence_payload = (tmp_path / "decision_signals.jsonl").read_text(encoding="utf-8")
    assert result["evidence_id"] in evidence_payload
