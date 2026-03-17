"""
tests/test_model_validation.py — unit tests for model validation.

All provider calls are mocked — no API keys or network required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from providers.base_provider import (
    AnthropicProvider,
    OllamaProvider,
    OpenAIProvider,
    ModelValidationError,
    validate_active_model,
)


def _config(**kwargs):
    """Return a minimal AgentConfig-like object for testing."""
    cfg = MagicMock()
    cfg.anthropic_api_key = "test-key"
    cfg.anthropic_model = kwargs.get("anthropic_model", "claude-sonnet-4-6")
    cfg.openai_api_key = "test-key"
    cfg.openai_model = kwargs.get("openai_model", "gpt-4o-mini")
    cfg.ollama_base_url = "http://localhost:11434"
    cfg.ollama_model = kwargs.get("ollama_model", "llama3.2")
    return cfg


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

def test_anthropic_valid_model():
    cfg = _config()
    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.models.retrieve.return_value = MagicMock()
        AnthropicProvider(cfg).validate_model()  # should not raise


def test_anthropic_invalid_model():
    import anthropic
    cfg = _config(anthropic_model="claude-does-not-exist")
    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.models.retrieve.side_effect = anthropic.NotFoundError(
            message="model not found", response=MagicMock(), body={}
        )
        with pytest.raises(ModelValidationError, match="claude-does-not-exist"):
            AnthropicProvider(cfg).validate_model()


def test_anthropic_bad_credentials():
    import anthropic
    cfg = _config()
    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.models.retrieve.side_effect = anthropic.AuthenticationError(
            message="invalid key", response=MagicMock(), body={}
        )
        with pytest.raises(ModelValidationError, match="authentication failed"):
            AnthropicProvider(cfg).validate_model()


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

def test_openai_valid_model():
    cfg = _config()
    with patch("openai.OpenAI") as mock_client:
        mock_client.return_value.models.retrieve.return_value = MagicMock()
        OpenAIProvider(cfg).validate_model()  # should not raise


def test_openai_invalid_model():
    import openai
    cfg = _config(openai_model="gpt-not-a-model")
    with patch("openai.OpenAI") as mock_client:
        mock_client.return_value.models.retrieve.side_effect = openai.NotFoundError(
            message="model not found", response=MagicMock(), body={}
        )
        with pytest.raises(ModelValidationError, match="gpt-not-a-model"):
            OpenAIProvider(cfg).validate_model()


def test_openai_bad_credentials():
    import openai
    cfg = _config()
    with patch("openai.OpenAI") as mock_client:
        mock_client.return_value.models.retrieve.side_effect = openai.AuthenticationError(
            message="invalid key", response=MagicMock(), body={}
        )
        with pytest.raises(ModelValidationError, match="authentication failed"):
            OpenAIProvider(cfg).validate_model()


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def test_ollama_valid_model():
    cfg = _config()
    with patch("ollama.Client") as mock_client:
        mock_client.return_value.show.return_value = MagicMock()
        OllamaProvider(cfg).validate_model()  # should not raise


def test_ollama_model_not_pulled():
    import ollama
    cfg = _config(ollama_model="llama-not-pulled")
    with patch("ollama.Client") as mock_client:
        mock_client.return_value.show.side_effect = ollama.ResponseError("model not found")
        with pytest.raises(ModelValidationError, match="llama-not-pulled"):
            OllamaProvider(cfg).validate_model()


def test_ollama_server_unreachable():
    cfg = _config()
    with patch("ollama.Client") as mock_client:
        mock_client.return_value.show.side_effect = ConnectionError("connection refused")
        with pytest.raises(ModelValidationError, match="could not reach server"):
            OllamaProvider(cfg).validate_model()


# ---------------------------------------------------------------------------
# validate_active_model factory
# ---------------------------------------------------------------------------

def test_validate_active_model_delegates_to_correct_provider():
    from agent.config import Provider
    cfg = _config()
    cfg.active_provider = Provider.openai

    with patch("openai.OpenAI") as mock_client:
        mock_client.return_value.models.retrieve.return_value = MagicMock()
        validate_active_model(cfg)  # should not raise
