"""
providers/base_provider.py — provider abstraction and factory.

Each concrete builder constructs a Strands Model object for one LLM provider.
The factory function `get_strands_model` is the single entry point used by
the workflow — callers never import a provider class directly.

Adding a new provider:
  1. Add a value to the Provider enum in agent/config.py
  2. Subclass BaseProviderBuilder and implement build()
  3. Register it in _PROVIDER_MAP
  4. Add required env vars to .env.example
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from agent.config import AgentConfig, Provider

if TYPE_CHECKING:
    # strands.models.Model is the shared base for all Strands model objects.
    # Imported under TYPE_CHECKING so this module remains importable even when
    # strands-agents is not installed (e.g. during unit tests or lint runs).
    from strands.models import Model


class ProviderImportError(RuntimeError):
    """Raised when a provider's Strands integration cannot be imported."""


class ModelValidationError(RuntimeError):
    """Raised when a provider rejects or cannot find the configured model ID."""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseProviderBuilder(ABC):
    """Constructs a configured Strands Model object for one provider."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    @abstractmethod
    def build(self) -> "Model":
        """Return a configured Strands Model instance."""

    @abstractmethod
    def validate_model(self) -> None:
        """
        Preflight check: verify the model ID is known and credentials are accepted.

        Makes a lightweight metadata call to the provider — does not execute the
        engineering workflow or generate completion tokens. Catches wrong model names
        and auth failures early, but does not guarantee full runtime compatibility
        (e.g. tool-calling support or endpoint-level behaviour).
        Raises ModelValidationError if the model is not found or the credential is rejected.
        """


# ---------------------------------------------------------------------------
# Concrete builders
# ---------------------------------------------------------------------------

class AnthropicProvider(BaseProviderBuilder):
    """Builds a Strands AnthropicModel using the Anthropic API."""

    def build(self) -> "Model":
        try:
            from strands.models.anthropic import AnthropicModel
        except ImportError as exc:
            raise ProviderImportError(
                "Could not import strands.models.anthropic. "
                "Ensure strands-agents is installed: pip install strands-agents"
            ) from exc

        # model_id and max_tokens are Required fields in AnthropicConfig.
        return AnthropicModel(
            client_args={"api_key": self.config.anthropic_api_key},
            model_id=self.config.anthropic_model,
            max_tokens=self.config.anthropic_max_tokens,
        )

    def validate_model(self) -> None:
        """Retrieve model metadata from the Anthropic API. Does not generate completion tokens."""
        import anthropic
        model_id = self.config.anthropic_model
        try:
            anthropic.Anthropic(api_key=self.config.anthropic_api_key).models.retrieve(model_id)
        except anthropic.NotFoundError:
            raise ModelValidationError(
                f"anthropic: model '{model_id}' not found. "
                "Check ANTHROPIC_MODEL in your .env file."
            )
        except anthropic.AuthenticationError as exc:
            raise ModelValidationError(
                f"anthropic: authentication failed — check ANTHROPIC_API_KEY. ({exc})"
            )
        except Exception as exc:
            raise ModelValidationError(
                f"anthropic: model validation failed for '{model_id}': {exc}"
            )


class OpenAIProvider(BaseProviderBuilder):
    """Builds a Strands OpenAIModel using the OpenAI API."""

    def build(self) -> "Model":
        try:
            from strands.models.openai import OpenAIModel
        except ImportError as exc:
            raise ProviderImportError(
                "Could not import strands.models.openai. "
                "Ensure strands-agents is installed: pip install strands-agents"
            ) from exc

        # client_args passes auth; model_id is an OpenAIConfig kwarg.
        return OpenAIModel(
            client_args={"api_key": self.config.openai_api_key},
            model_id=self.config.openai_model,
        )

    def validate_model(self) -> None:
        """Retrieve model metadata from the OpenAI API. Does not generate completion tokens."""
        import openai
        model_id = self.config.openai_model
        try:
            openai.OpenAI(api_key=self.config.openai_api_key).models.retrieve(model_id)
        except openai.NotFoundError:
            raise ModelValidationError(
                f"openai: model '{model_id}' not found. "
                "Check OPENAI_MODEL in your .env file."
            )
        except openai.AuthenticationError as exc:
            raise ModelValidationError(
                f"openai: authentication failed — check OPENAI_API_KEY. ({exc})"
            )
        except Exception as exc:
            raise ModelValidationError(
                f"openai: model validation failed for '{model_id}': {exc}"
            )



class OllamaProvider(BaseProviderBuilder):
    """
    Builds a Strands OllamaModel pointed at OLLAMA_BASE_URL.

    No API key is required. The default URL (http://ollama:11434) matches the
    Docker Compose service name. Override with OLLAMA_BASE_URL=http://localhost:11434
    for a native Ollama install.
    """

    def build(self) -> "Model":
        try:
            from strands.models.ollama import OllamaModel
        except ImportError as exc:
            raise ProviderImportError(
                "Could not import strands.models.ollama. "
                "Ensure strands-agents is installed: pip install strands-agents"
            ) from exc

        return OllamaModel(
            host=self.config.ollama_base_url,
            model_id=self.config.ollama_model,
        )

    def validate_model(self) -> None:
        """Check the model is pulled in the local Ollama server. Does not generate completion tokens."""
        import ollama
        model_id = self.config.ollama_model
        url = self.config.ollama_base_url
        try:
            ollama.Client(host=url).show(model_id)
        except ollama.ResponseError as exc:
            raise ModelValidationError(
                f"ollama: model '{model_id}' not available at {url}. "
                f"Run: ollama pull {model_id}  ({exc})"
            )
        except Exception as exc:
            raise ModelValidationError(
                f"ollama: could not reach server at {url} for model '{model_id}': {exc}"
            )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDER_MAP: dict[Provider, type[BaseProviderBuilder]] = {
    Provider.anthropic: AnthropicProvider,
    Provider.openai: OpenAIProvider,
    Provider.ollama: OllamaProvider,
}


def validate_active_model(config: AgentConfig) -> None:
    """
    Preflight check: verify the active provider's model ID is known and credentials
    are accepted before a run starts.

    Makes a lightweight metadata call — does not execute the engineering workflow
    or generate completion tokens. Catches wrong model names and auth failures early,
    but does not guarantee full runtime compatibility (e.g. tool-calling support).
    Raises ModelValidationError on failure.
    Call this from `agent doctor` and at the top of `agent run`.
    """
    provider = config.active_provider
    builder_cls = _PROVIDER_MAP.get(provider)
    if builder_cls is None:
        raise ValueError(f"No builder registered for provider '{provider}'.")
    builder_cls(config).validate_model()


def get_strands_model(config: AgentConfig) -> "Model":
    """
    Return a configured Strands Model for the active provider.

    Reads config.active_provider and delegates to the registered builder.
    Raises ProviderImportError if the Strands integration cannot be imported.
    Raises ValueError if no builder is registered for the provider (should not
    occur after Pydantic validation, but kept as an explicit safety net).
    """
    provider = config.active_provider
    builder_cls = _PROVIDER_MAP.get(provider)

    if builder_cls is None:
        raise ValueError(
            f"No builder registered for provider '{provider}'. "
            f"Registered providers: {[p.value for p in _PROVIDER_MAP]}"
        )

    return builder_cls(config).build()
