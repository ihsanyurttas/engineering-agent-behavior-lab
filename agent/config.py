"""
agent/config.py — environment-driven configuration with validation.

All runtime settings come from environment variables.
No secrets are ever hardcoded here.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class Provider(str, Enum):
    anthropic = "anthropic"
    openai = "openai"
    ollama = "ollama"


class AgentRuntime(str, Enum):
    """
    Describes the execution environment.

    This is informational for Phase 1 — no runtime branching happens on this
    value yet. It is intended for future use when behaviour needs to differ
    between local execution, Docker, and Kubernetes (e.g. service discovery,
    volume paths, health-check endpoints).
    """

    local = "local"
    docker = "docker"
    kubernetes = "kubernetes"


class AgentConfig(BaseSettings):
    """
    Single source of truth for all runtime configuration.

    Values are read from environment variables (or a .env file if present).
    Required fields that are missing raise a clear ValidationError at startup —
    never silently at use time.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Provider selection
    # Field name matches the DEFAULT_PROVIDER env var via pydantic-settings
    # name mapping. Use the active_provider property at callsites.
    # ------------------------------------------------------------------
    default_provider: Provider = Field(
        default=Provider.anthropic,
        description="Active provider: anthropic | openai | ollama",
    )

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------
    anthropic_api_key: str | None = Field(default=None, repr=False)
    anthropic_model: str = Field(default="claude-sonnet-4-6")

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_model: str = Field(default="gpt-4o")

    # ------------------------------------------------------------------
    # Ollama  (container-friendly defaults)
    # ------------------------------------------------------------------
    ollama_base_url: str = Field(default="http://ollama:11434")
    ollama_model: str = Field(default="llama3")

    # ------------------------------------------------------------------
    # Runtime behaviour
    # ------------------------------------------------------------------
    agent_runtime: AgentRuntime = Field(default=AgentRuntime.local)
    log_level: str = Field(default="INFO")
    max_iterations: int = Field(default=10, ge=1, le=100)

    # Stored as str so pydantic-settings can read them from env vars directly.
    # Use the Path-typed properties below in application code.
    results_dir: str = Field(default="eval/results")
    sample_repo_path: str = Field(default="./sample_repos")

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        upper = v.upper()
        if upper not in _VALID_LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL must be one of {_VALID_LOG_LEVELS}, got '{v}'")
        return upper

    @model_validator(mode="after")
    def validate_provider_credentials(self) -> AgentConfig:
        """Fail fast if the active provider is missing its required credential."""
        provider = self.active_provider

        if provider == Provider.anthropic and not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when DEFAULT_PROVIDER=anthropic. "
                "Set it in your .env file or environment."
            )

        if provider == Provider.openai and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when DEFAULT_PROVIDER=openai. "
                "Set it in your .env file or environment."
            )

        if provider == Provider.ollama and not self.ollama_base_url:
            raise ValueError(
                "OLLAMA_BASE_URL must be set when DEFAULT_PROVIDER=ollama. "
                "Typical value: http://ollama:11434 (Docker) or http://localhost:11434 (native)."
            )

        return self

    # ------------------------------------------------------------------
    # Runtime accessors
    # ------------------------------------------------------------------
    @property
    def active_provider(self) -> Provider:
        """
        The provider selected for this run.

        `default_provider` is the pydantic-settings field name that maps to the
        DEFAULT_PROVIDER env var. `active_provider` is the accessor used
        everywhere in application code so callsites express intent, not the
        config field name.
        """
        return self.default_provider

    def active_model(self) -> str:
        """Return the model ID for the active provider."""
        return {
            Provider.anthropic: self.anthropic_model,
            Provider.openai: self.openai_model,
            Provider.ollama: self.ollama_model,
        }[self.active_provider]

    @property
    def results_path(self) -> Path:
        """results_dir as a resolved Path. Use this in application code."""
        return Path(self.results_dir).resolve()

    @property
    def sample_repo_root(self) -> Path:
        """sample_repo_path as a resolved Path. Use this in application code."""
        return Path(self.sample_repo_path).resolve()

    # ------------------------------------------------------------------
    # Doctor report
    # ------------------------------------------------------------------
    def doctor_report(self) -> dict[str, str]:
        """
        Return a health summary focused on the active provider.

        Leads with what matters for the current run (active provider, model,
        its credential status), then shows secondary context. Safe to display —
        no secret values are included.
        """
        provider = self.active_provider

        credential_status = {
            Provider.anthropic: "set" if self.anthropic_api_key else "NOT SET",
            Provider.openai: "set" if self.openai_api_key else "NOT SET",
            Provider.ollama: "n/a (no key required)",
        }

        return {
            # Active provider context — most important
            "active_provider": provider.value,
            "active_model": self.active_model(),
            "credential": credential_status[provider],
            # Ollama endpoint shown when relevant
            **({"ollama_base_url": self.ollama_base_url} if provider == Provider.ollama else {}),
            # Runtime context
            "agent_runtime": self.agent_runtime.value,
            "log_level": self.log_level,
            "max_iterations": str(self.max_iterations),
            "results_dir": self.results_dir,
        }


def load_config() -> AgentConfig:
    """Load and validate config from the environment. Call once at startup."""
    return AgentConfig()
