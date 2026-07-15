from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.config import Settings
from app.services.evidence import EvidenceIndex
from app.services.qa_pipeline import LlmResult, QuestionAnsweringPipeline
from app.services.retrieval import (
    DeepSearchService,
    GraphitiAdvancedSearchAdapter,
    GraphitiCrossEncoderAdapter,
    Neo4jLexicalSearchAdapter,
    SiliconFlowReranker,
)
from app.services.trust import EvidenceGate, TrustBuilder
from app.services.tracing import start_span
from app.storage import Repository


class OpenAICompatibleChatClient:
    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def rewrite(
        self, question: str, history: list[dict[str, str]]
    ) -> LlmResult:
        history_text = "\n".join(
            f"{item['role']}：{item['content']}" for item in history
        )
        with start_span(
            "llm.rewrite",
            {
                "model": self.model,
                "history_turns": len(history),
                "question_length": len(question),
            },
        ):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是知识图谱检索问题改写器。只消解代词和补全上下文，"
                            "不得增加原问题没有的事实或限制。只返回一行改写后的问题。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"历史对话：\n{history_text}\n\n当前问题：{question}",
                    },
                ],
                temperature=0,
            )
        return _llm_result(response)

    async def answer(self, question: str, context: str) -> LlmResult:
        with start_span(
            "llm.answer",
            {
                "model": self.model,
                "question_length": len(question),
                "context_length": len(context),
            },
        ):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是严谨的半导体产业知识图谱问答助手。只能使用给定图谱事实；"
                            "关键结论后必须用方括号标注证据ID。若事实标记潜在匹配、推定关系"
                            "或需要内部验证，必须明确说明不能当作已确认客户或交易关系。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"问题：{question}\n\n图谱事实：\n{context}",
                    },
                ],
                temperature=0,
            )
        return _llm_result(response)

    async def close(self) -> None:
        await self.client.close()


def _llm_result(response: Any) -> LlmResult:
    text = str(response.choices[0].message.content or "").strip()
    if not text:
        raise ValueError("大模型返回空回答")
    usage = getattr(response, "usage", None)
    return LlmResult(
        text=text,
        request_tokens=getattr(usage, "prompt_tokens", None),
        response_tokens=getattr(usage, "completion_tokens", None),
    )


def build_graphiti(settings: Settings, cross_encoder: Any | None = None):
    if not settings.siliconflow_api_key:
        raise RuntimeError("SILICONFLOW_API_KEY 未配置")

    from graphiti_core import Graphiti
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    from graphiti_core.llm_client import LLMConfig
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

    llm_config = LLMConfig(
        api_key=settings.siliconflow_api_key,
        model=settings.llm_model,
        small_model=settings.llm_model,
        base_url=settings.llm_base_url,
        temperature=0,
    )
    graphiti_llm = OpenAIGenericClient(
        config=llm_config, structured_output_mode="json_object"
    )
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=settings.siliconflow_api_key,
            base_url=settings.embedding_base_url,
            embedding_model=settings.embedding_model,
        )
    )
    graphiti_kwargs: dict[str, Any] = {
        "llm_client": graphiti_llm,
        "embedder": embedder,
        "cross_encoder": cross_encoder
        or SiliconFlowReranker(
            api_key=settings.siliconflow_api_key,
            base_url=settings.llm_base_url,
            model=settings.reranker_model,
        ),
    }
    return Graphiti(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
        **graphiti_kwargs,
    )


def build_default_pipeline(
    settings: Settings, repository: Repository
) -> QuestionAnsweringPipeline:
    if not settings.siliconflow_api_key:
        raise RuntimeError("SILICONFLOW_API_KEY 未配置")

    graphiti_reranker = SiliconFlowReranker(
        api_key=settings.siliconflow_api_key,
        base_url=settings.llm_base_url,
        model=settings.reranker_model,
    )
    graphiti = build_graphiti(settings, cross_encoder=graphiti_reranker)
    search_service = DeepSearchService(
        GraphitiAdvancedSearchAdapter(graphiti, group_id=settings.group_id),
        Neo4jLexicalSearchAdapter(graphiti.driver, settings.group_id),
        GraphitiCrossEncoderAdapter(graphiti_reranker),
        group_id=settings.group_id,
        slice_limit=settings.retrieval_slice_limit,
        candidate_pool_limit=settings.candidate_pool_limit,
        final_limit=settings.final_result_limit,
        search_timeout_seconds=settings.search_timeout_seconds,
    )
    evidence_index = EvidenceIndex()
    return QuestionAnsweringPipeline(
        repository=repository,
        search_service=search_service,
        evidence_gate=EvidenceGate(evidence_index),
        trust_builder=TrustBuilder(evidence_index),
        chat_client=OpenAICompatibleChatClient(
            api_key=settings.siliconflow_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        ),
        model=settings.llm_model,
        graphiti=graphiti,
    )
