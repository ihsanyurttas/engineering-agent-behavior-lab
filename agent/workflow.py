"""
agent/workflow.py — Strands-based orchestration loop.

The same 4-phase workflow runs against any provider by injecting a different
Strands Model object. This module never imports a provider directly.

Phase order:
  1. inspect     — read repo files, identify the root cause
  2. plan        — produce a numbered implementation plan
  3. implement   — generate code changes
  4. self_review — the agent reviews its own output and scores confidence
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agent.config import AgentConfig
from agent.prompts import (
    SYSTEM_PROMPT,
    implement_prompt,
    inspect_prompt,
    plan_prompt,
    self_review_prompt,
)
from eval.result_schema import PhaseResult, WorkflowResult
from providers.base_provider import get_strands_model

if TYPE_CHECKING:
    from strands import Agent

logger = logging.getLogger(__name__)


@dataclass
class WorkflowContext:
    """Accumulates outputs as the workflow progresses through phases."""

    issue: str
    repo_path: str
    provider: str
    model: str

    inspection: str = ""
    plan: str = ""
    implementation: str = ""
    self_review: str = ""
    phase_results: list[PhaseResult] = field(default_factory=list)


def run_workflow(issue: str, repo_path: str, config: AgentConfig) -> WorkflowResult:
    """
    Execute the full 4-phase engineering workflow for a given issue.

    Args:
        issue:     Natural-language description of the engineering task.
        repo_path: Path to the repository to inspect (relative or absolute).
        config:    Validated agent configuration.

    Returns:
        WorkflowResult with all phase outputs, timing, and token metrics.
    """
    # Lazy import so the rest of the codebase is importable without strands installed.
    try:
        from strands import Agent
        from tools.repo_reader import list_files, read_file
        from tools.search_tools import search_in_repo
        from tools.patch_writer import write_patch
    except ImportError as exc:
        raise RuntimeError(
            "strands-agents is not installed. Run: pip install strands-agents"
        ) from exc

    model = get_strands_model(config)
    ctx = WorkflowContext(
        issue=issue,
        repo_path=repo_path,
        provider=config.active_provider.value,
        model=config.active_model(),
    )

    workflow_start = time.perf_counter()

    # A single Agent instance is shared across all phases intentionally:
    # Strands preserves conversation history on the instance, so each phase
    # has full context from all prior phases without re-injecting it manually.
    # max_iterations controls the tool-use loop depth per Agent invocation;
    # Strands configures this at the Agent level, not per-call.
    agent: Agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[read_file, list_files, search_in_repo, write_patch],
        max_parallel_tool_uses=1,  # sequential — ensures deterministic output for comparison
        max_iterations=config.max_iterations,
    )

    # ------------------------------------------------------------------
    # Phase 1: Inspect
    # ------------------------------------------------------------------
    output, phase_result = _run_phase(
        agent=agent,
        ctx=ctx,
        phase_name="inspect",
        prompt=inspect_prompt(ctx.issue, ctx.repo_path),
    )
    ctx.inspection = output
    ctx.phase_results.append(phase_result)

    # ------------------------------------------------------------------
    # Phase 2: Plan
    # ------------------------------------------------------------------
    output, phase_result = _run_phase(
        agent=agent,
        ctx=ctx,
        phase_name="plan",
        prompt=plan_prompt(ctx.issue, ctx.inspection),
    )
    ctx.plan = output
    ctx.phase_results.append(phase_result)

    # ------------------------------------------------------------------
    # Phase 3: Implement
    # ------------------------------------------------------------------
    output, phase_result = _run_phase(
        agent=agent,
        ctx=ctx,
        phase_name="implement",
        prompt=implement_prompt(ctx.issue, ctx.inspection, ctx.plan),
    )
    ctx.implementation = output
    ctx.phase_results.append(phase_result)

    # ------------------------------------------------------------------
    # Phase 4: Self-review
    # ------------------------------------------------------------------
    output, phase_result = _run_phase(
        agent=agent,
        ctx=ctx,
        phase_name="self_review",
        prompt=self_review_prompt(ctx.issue, ctx.implementation),
    )
    ctx.self_review = output
    ctx.phase_results.append(phase_result)

    total_elapsed = time.perf_counter() - workflow_start

    # Accumulate token counts from phases that reported them.
    total_input = sum(p.input_tokens or 0 for p in ctx.phase_results)
    total_output = sum(p.output_tokens or 0 for p in ctx.phase_results)

    return WorkflowResult(
        provider=ctx.provider,
        model=ctx.model,
        issue=ctx.issue,
        repo_path=ctx.repo_path,
        phases=ctx.phase_results,
        total_elapsed_seconds=round(total_elapsed, 3),
        total_input_tokens=total_input or None,
        total_output_tokens=total_output or None,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_phase(
    agent: Agent,
    ctx: WorkflowContext,
    phase_name: str,
    prompt: str,
) -> tuple[str, PhaseResult]:
    """
    Invoke the agent for one phase and return (output_text, PhaseResult).

    Token counts are extracted from the AgentResult before converting to str.
    The caller assigns the output text to the appropriate WorkflowContext field.
    """
    logger.info("[%s] Starting phase: %s", ctx.provider, phase_name)
    start = time.perf_counter()

    result = agent(prompt)

    elapsed = time.perf_counter() - start

    # Extract token usage before stringifying. Strands AgentResult exposes
    # usage as result.usage with inputTokens / outputTokens (camelCase).
    # Use getattr with fallbacks so missing fields never raise.
    usage = getattr(result, "usage", None)
    input_tokens: int | None = getattr(usage, "inputTokens", None)
    output_tokens: int | None = getattr(usage, "outputTokens", None)

    output_text = str(result)

    logger.info(
        "[%s] Phase '%s' done in %.2fs — %d chars, in=%s out=%s tokens",
        ctx.provider, phase_name, elapsed, len(output_text),
        input_tokens, output_tokens,
    )

    return output_text, PhaseResult(
        phase=phase_name,
        prompt=prompt,
        output=output_text,
        elapsed_seconds=round(elapsed, 3),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
