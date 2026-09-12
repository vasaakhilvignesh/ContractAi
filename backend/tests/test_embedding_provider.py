"""
ContractIQ — Embedding Provider Unit Tests (Phase 4A)

Strict requirements:
  - 100% Mocked: Zero real Gemini API calls.
  - Zero real API keys required.
  - N inputs -> N outputs with preserved ordering.
  - Exactly 768 dimensions.
  - Task types: RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY.
  - Robust batching and error handling.
  - Zero leakage of raw contract text or credentials in error messages.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.config import Settings
from app.services.embedding_factory import get_embedding_provider
from app.services.embedding_provider import (
    EmbeddingConfigurationError,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingTaskType,
    EmbeddingValidationError,
)
from app.services.gemini_embedding_provider import GeminiEmbeddingProvider


# Helper to build a mock embedding object with 768 floats
def _make_mock_embedding(dim: int = 768, seed_val: float = 0.1) -> MagicMock:
    emb = MagicMock()
    emb.values = [seed_val + (i * 0.001) for i in range(dim)]
    return emb


def _make_mock_response(num_embeddings: int, dim: int = 768, base_val: float = 0.1) -> MagicMock:
    resp = MagicMock()
    resp.embeddings = [
        _make_mock_embedding(dim=dim, seed_val=base_val + (idx * 0.05))
        for idx in range(num_embeddings)
    ]
    return resp


@pytest.fixture
def mock_genai_client():
    """Returns a mocked google-genai Client with async embed_content."""
    client = MagicMock()
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    client.aio.models.embed_content = AsyncMock()
    return client


@pytest.fixture
def provider(mock_genai_client):
    """Returns a GeminiEmbeddingProvider configured with a mock client."""
    return GeminiEmbeddingProvider(
        api_key="test-dummy-api-key-12345678",
        model_name="gemini-embedding-2",
        dimension=768,
        batch_size=3,
        client=mock_genai_client,
    )


# ====================================================================
# 1. Configuration & Factory Tests
# ====================================================================

class TestEmbeddingConfiguration:
    def test_missing_api_key_raises_configuration_error(self):
        with patch("app.services.gemini_embedding_provider.settings.gemini_api_key", ""):
            with pytest.raises(EmbeddingConfigurationError) as exc_info:
                GeminiEmbeddingProvider(api_key="")
            assert "Gemini API key is not configured" in str(exc_info.value)

    def test_invalid_dimension_raises_configuration_error(self, mock_genai_client):
        with pytest.raises(EmbeddingConfigurationError) as exc_info:
            GeminiEmbeddingProvider(
                api_key="test-key",
                dimension=1536,
                client=mock_genai_client,
            )
        assert "768 dimensions" in str(exc_info.value)

    def test_obsolete_or_invalid_model_raises_configuration_error(self, mock_genai_client):
        with pytest.raises(EmbeddingConfigurationError) as exc_info:
            GeminiEmbeddingProvider(
                api_key="test-key",
                model_name="text-embedding-004",  # Obsolete model explicitly forbidden
                client=mock_genai_client,
            )
        assert "gemini-embedding-2" in str(exc_info.value)

    def test_factory_returns_gemini_provider(self, mock_genai_client):
        with patch("app.services.embedding_factory.GeminiEmbeddingProvider") as mock_cls:
            mock_instance = MagicMock(spec=EmbeddingProvider)
            mock_cls.return_value = mock_instance

            prov = get_embedding_provider(
                provider_name="gemini",
                api_key="test-dummy-key",
            )
            assert prov == mock_instance
            mock_cls.assert_called_once()

    def test_factory_unsupported_provider_raises_error(self):
        with pytest.raises(EmbeddingConfigurationError) as exc_info:
            get_embedding_provider(provider_name="unsupported_provider")
        assert "Unsupported embedding provider" in str(exc_info.value)

    def test_secret_hygiene_in_config(self):
        s = Settings(gemini_api_key="AIzaSyDummySecretKey1234567890")
        summary = s.safe_gemini_key_summary
        assert "AIza" in summary
        assert "7890" in summary
        assert "SyDummySecretKey123456" not in summary
        assert s.is_gemini_configured is True

    def test_secret_hygiene_when_key_empty(self):
        s = Settings(gemini_api_key="")
        assert s.safe_gemini_key_summary == "<not configured>"
        assert s.is_gemini_configured is False


# ====================================================================
# 2. Input Validation Tests
# ====================================================================

class TestEmbeddingValidation:
    @pytest.mark.asyncio
    async def test_empty_list_returns_empty_immediately(self, provider, mock_genai_client):
        result = await provider.embed_texts([])
        assert result == []
        mock_genai_client.aio.models.embed_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_list_texts_raises_validation_error(self, provider):
        with pytest.raises(EmbeddingValidationError) as exc:
            await provider.embed_texts("not a list")  # type: ignore[arg-type]
        assert "must be a list" in str(exc.value)

    @pytest.mark.asyncio
    async def test_none_texts_raises_validation_error(self, provider):
        with pytest.raises(EmbeddingValidationError) as exc:
            await provider.embed_texts(None)  # type: ignore[arg-type]
        assert "cannot be None" in str(exc.value)

    @pytest.mark.asyncio
    async def test_list_with_non_string_item_raises_validation_error(self, provider):
        with pytest.raises(EmbeddingValidationError) as exc:
            await provider.embed_texts(["valid text", 12345])  # type: ignore[list-item]
        assert "is not a string" in str(exc.value)

    @pytest.mark.asyncio
    async def test_list_with_whitespace_only_raises_validation_error(self, provider):
        with pytest.raises(EmbeddingValidationError) as exc:
            await provider.embed_texts(["valid clause", "   \n\t  "])
        assert "empty or contains only whitespace" in str(exc.value)

    @pytest.mark.asyncio
    async def test_unsupported_task_type_raises_validation_error(self, provider):
        with pytest.raises(EmbeddingValidationError) as exc:
            await provider.embed_texts(["valid clause"], task_type="UNSUPPORTED_TASK")
        assert "Unsupported task type" in str(exc.value)

    @pytest.mark.asyncio
    async def test_embed_query_empty_raises_validation_error(self, provider):
        with pytest.raises(EmbeddingValidationError) as exc:
            await provider.embed_query("   ")
        assert "must be a non-empty string" in str(exc.value)


# ====================================================================
# 3. N -> N Mapping, Ordering & Dimension Guarantees
# ====================================================================

class TestEmbeddingExecutionAndOrdering:
    @pytest.mark.asyncio
    async def test_single_text_embedding(self, provider, mock_genai_client):
        mock_genai_client.aio.models.embed_content.return_value = _make_mock_response(1, dim=768, base_val=0.5)

        results = await provider.embed_texts(["This is clause 1."])
        assert len(results) == 1
        assert len(results[0]) == 768
        assert results[0][0] == pytest.approx(0.5, abs=1e-4)

    @pytest.mark.asyncio
    async def test_n_to_n_ordering_within_single_batch(self, provider, mock_genai_client):
        # 3 items, batch_size=3 -> 1 batch call
        mock_genai_client.aio.models.embed_content.return_value = _make_mock_response(3, dim=768, base_val=0.1)

        inputs = ["Clause A", "Clause B", "Clause C"]
        results = await provider.embed_texts(inputs)

        assert len(results) == 3
        # In _make_mock_response, base_val + (idx * 0.05)
        # item 0 first float ~ 0.10
        # item 1 first float ~ 0.15
        # item 2 first float ~ 0.20
        assert results[0][0] == pytest.approx(0.10, abs=1e-4)
        assert results[1][0] == pytest.approx(0.15, abs=1e-4)
        assert results[2][0] == pytest.approx(0.20, abs=1e-4)
        assert all(len(emb) == 768 for emb in results)

    @pytest.mark.asyncio
    async def test_multi_batch_ordering_preserved(self, provider, mock_genai_client):
        # batch_size=3. Passing 7 items should result in 3 batches: [3, 3, 1]
        mock_genai_client.aio.models.embed_content.side_effect = [
            _make_mock_response(3, dim=768, base_val=0.10),  # batch 1 (items 0, 1, 2)
            _make_mock_response(3, dim=768, base_val=0.30),  # batch 2 (items 3, 4, 5)
            _make_mock_response(1, dim=768, base_val=0.50),  # batch 3 (item 6)
        ]

        inputs = [f"Clause {i}" for i in range(7)]
        results = await provider.embed_texts(inputs)

        assert len(results) == 7
        assert mock_genai_client.aio.models.embed_content.call_count == 3

        # Verify batch 1 results
        assert results[0][0] == pytest.approx(0.10, abs=1e-4)
        assert results[1][0] == pytest.approx(0.15, abs=1e-4)
        assert results[2][0] == pytest.approx(0.20, abs=1e-4)

        # Verify batch 2 results
        assert results[3][0] == pytest.approx(0.30, abs=1e-4)
        assert results[4][0] == pytest.approx(0.35, abs=1e-4)
        assert results[5][0] == pytest.approx(0.40, abs=1e-4)

        # Verify batch 3 results
        assert results[6][0] == pytest.approx(0.50, abs=1e-4)

        for emb in results:
            assert len(emb) == 768

    @pytest.mark.asyncio
    async def test_embed_query_task_type_and_dimension(self, provider, mock_genai_client):
        mock_genai_client.aio.models.embed_content.return_value = _make_mock_response(1, dim=768, base_val=0.9)

        query_vec = await provider.embed_query("What is the governing law?")
        assert len(query_vec) == 768
        assert query_vec[0] == pytest.approx(0.9, abs=1e-4)

        # Verify task_type passed to SDK config was RETRIEVAL_QUERY
        call_kwargs = mock_genai_client.aio.models.embed_content.call_args.kwargs
        assert call_kwargs["config"].task_type == "RETRIEVAL_QUERY"
        assert call_kwargs["config"].output_dimensionality == 768

    @pytest.mark.asyncio
    async def test_retrieval_document_task_type_with_title(self, provider, mock_genai_client):
        mock_genai_client.aio.models.embed_content.return_value = _make_mock_response(1, dim=768, base_val=0.2)

        await provider.embed_texts(
            texts=["Section 1. Definitions"],
            task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
            title="Master Services Agreement",
        )

        call_kwargs = mock_genai_client.aio.models.embed_content.call_args.kwargs
        assert call_kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"
        assert call_kwargs["config"].title == "Master Services Agreement"
        assert call_kwargs["config"].output_dimensionality == 768


# ====================================================================
# 4. Error Handling & Privacy Guarantees
# ====================================================================

class TestEmbeddingErrorHandlingAndSecurity:
    @pytest.mark.asyncio
    async def test_upstream_api_failure_wrapped_in_provider_error(self, provider, mock_genai_client):
        mock_genai_client.aio.models.embed_content.side_effect = RuntimeError("Service Unavailable 503")

        with pytest.raises(EmbeddingProviderError) as exc_info:
            await provider.embed_texts(["Confidential NDA clause"])

        assert "Gemini embedding request failed" in str(exc_info.value)
        assert "Service Unavailable" in str(exc_info.value)
        # Verify raw text is not exposed in the error message
        assert "Confidential NDA clause" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_response_count_mismatch_raises_error(self, provider, mock_genai_client):
        # Send 2 texts, but response contains only 1 embedding
        mock_genai_client.aio.models.embed_content.return_value = _make_mock_response(1, dim=768)

        with pytest.raises(EmbeddingProviderError) as exc_info:
            await provider.embed_texts(["Clause 1", "Clause 2"])
        assert "Embedding count mismatch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dimension_mismatch_raises_error(self, provider, mock_genai_client):
        # Response has 384 dimensions instead of 768
        mock_genai_client.aio.models.embed_content.return_value = _make_mock_response(1, dim=384)

        with pytest.raises(EmbeddingProviderError) as exc_info:
            await provider.embed_texts(["Valid text"])
        assert "Embedding dimension mismatch" in str(exc_info.value)
        assert "expected 768" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_response_missing_embeddings_attribute(self, provider, mock_genai_client):
        bad_resp = MagicMock(spec=[])  # No embeddings attribute
        mock_genai_client.aio.models.embed_content.return_value = bad_resp

        with pytest.raises(EmbeddingProviderError) as exc_info:
            await provider.embed_texts(["Valid text"])
        assert "no embeddings field" in str(exc_info.value)
