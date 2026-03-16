"""
providers/provider_config.py — per-provider configuration requirements.

This module documents which environment variables each provider needs and
provides a helper used by `agent doctor` to surface missing values before
a run fails inside the provider builder.

What this module does:
  - Declares required and optional env vars per provider
  - Maps each required var to an explicit config field accessor
  - Returns human-readable issue strings (not exceptions) for display

What this module does NOT do:
  - Live connectivity checks (no HTTP calls)
  - Secret validation beyond presence
  - Anything that changes runtime behaviour
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from agent.config import AgentConfig, Provider


@dataclass(frozen=True)
class RequiredVar:
    """
    Maps one required environment variable to its AgentConfig field.

    env_var:   The name shown to the user (e.g. "ANTHROPIC_API_KEY").
    get_value: Extracts the live value from AgentConfig.
               Using a callable avoids fragile name-to-field reflection.
    """

    env_var: str
    get_value: Callable[[AgentConfig], str | None]


@dataclass(frozen=True)
class ProviderRequirements:
    """Configuration requirements for one provider."""

    name: str
    required: tuple[RequiredVar, ...]
    # Optional vars are listed for documentation and doctor output only.
    # They are not validated — absence is never an error.
    optional_env_vars: tuple[str, ...] = field(default=())
    notes: str = ""


PROVIDER_REQUIREMENTS: dict[Provider, ProviderRequirements] = {
    Provider.anthropic: ProviderRequirements(
        name="Anthropic",
        required=(
            RequiredVar("ANTHROPIC_API_KEY", lambda c: c.anthropic_api_key),
        ),
        optional_env_vars=("ANTHROPIC_MODEL",),
        notes="Uses the Anthropic Messages API via strands-agents.",
    ),
    Provider.openai: ProviderRequirements(
        name="OpenAI",
        required=(
            RequiredVar("OPENAI_API_KEY", lambda c: c.openai_api_key),
        ),
        optional_env_vars=("OPENAI_MODEL",),
        notes="Uses the OpenAI Chat Completions API via strands-agents.",
    ),
    Provider.ollama: ProviderRequirements(
        name="Ollama",
        required=(
            RequiredVar("OLLAMA_BASE_URL", lambda c: c.ollama_base_url),
            RequiredVar("OLLAMA_MODEL", lambda c: c.ollama_model),
        ),
        optional_env_vars=(),
        notes=(
            "No API key required. "
            "Ollama must be running at OLLAMA_BASE_URL before the agent starts. "
            "Recommended: docker compose up ollama, then ollama pull <model>."
        ),
    ),
}


def check_provider_requirements(config: AgentConfig) -> list[str]:
    """
    Return a list of issues for the active provider's required env vars.

    Each issue is a human-readable string describing one missing value.
    An empty list means all required vars are present (values are non-empty).

    Note: this checks presence only — it does not validate key format or
    test live connectivity.
    """
    provider = config.active_provider
    reqs = PROVIDER_REQUIREMENTS.get(provider)

    if reqs is None:
        return [f"No requirements registered for provider '{provider.value}'."]

    return [
        f"Missing required env var: {req.env_var}"
        for req in reqs.required
        if not req.get_value(config)
    ]
