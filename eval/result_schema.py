"""
eval/result_schema.py — Pydantic schema for structured workflow run results.

Each provider run produces one WorkflowResult that is serialised to JSON
in eval/results/. This enables apples-to-apples comparison across providers.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PhaseResult(BaseModel):
    """Output from a single workflow phase."""

    phase: str
    prompt: str
    output: str
    elapsed_seconds: float
    # Token counts extracted from the provider response, when available.
    input_tokens: int | None = None
    output_tokens: int | None = None


class WorkflowResult(BaseModel):
    """Complete result for one provider run on one task."""

    # Identity
    provider: str
    model: str
    issue: str
    repo_path: str

    # Phase outputs
    phases: list[PhaseResult]

    # Timing
    total_elapsed_seconds: float
    run_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Token totals summed across all phases (None when provider does not expose usage).
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    estimated_cost_usd: float | None = None

    # Confidence score (0–10) extracted from the self_review phase output.
    confidence_score: float | None = None

    def summary(self) -> dict:
        """Return a compact summary dict suitable for CLI display."""
        return {
            "provider": self.provider,
            "model": self.model,
            "total_elapsed_seconds": self.total_elapsed_seconds,
            "phases_completed": len(self.phases),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "confidence_score": self.confidence_score,
            "run_at": self.run_at.isoformat(),
        }
