"""
agent/prompts.py — prompt templates for each workflow phase.

Kept in one place so they can be iterated on independently of workflow logic.
All prompts are plain strings with f-string placeholders; no external templating
library is needed at this stage.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# System prompt — sets the agent's persona and constraints
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are a senior software engineer assistant.
Your job is to inspect a code repository, understand an engineering issue,
create an implementation plan, write or suggest code changes, and review
your own output before finalising.

Rules:
- Always read the relevant files before making changes.
- Write correct, idiomatic code for the language of the repository.
- Keep changes minimal and focused on the stated issue.
- Clearly explain your reasoning at each step.
- If you are unsure, say so — do not fabricate answers.
"""


# ---------------------------------------------------------------------------
# Phase prompts — injected at each stage of the workflow loop
# ---------------------------------------------------------------------------

def inspect_prompt(issue: str, repo_path: str) -> str:
    return f"""\
## Phase 1: Repository Inspection

Issue to solve:
{issue}

Repository path: {repo_path}

Read the relevant files and summarise:
1. What the repository does
2. Which files are relevant to the issue
3. What the root cause of the issue likely is
"""


def plan_prompt(issue: str, inspection_summary: str) -> str:
    return f"""\
## Phase 2: Implementation Plan

Issue:
{issue}

Inspection findings:
{inspection_summary}

Produce a numbered step-by-step implementation plan.
Be specific about which files to change and what changes to make.
"""


def implement_prompt(issue: str, inspection: str, plan: str) -> str:
    """
    Provide the original issue, inspection findings, and plan as context.
    The issue is the ground truth for what a correct implementation means.
    """
    return f"""\
## Phase 3: Implementation

Original issue:
{issue}

Inspection findings:
{inspection}

Implementation plan:
{plan}

For each step in the plan:
- Write the exact code changes needed
- Use a diff-style or full file replacement format
- Do not skip steps
"""


def self_review_prompt(issue: str, implementation: str) -> str:
    """
    Self-review by the same agent that produced the implementation.
    Including the original issue grounds the "does it solve the issue" check.
    """
    return f"""\
## Phase 4: Self-Review

Original issue:
{issue}

Implementation produced:
{implementation}

Review the implementation above. Check for:
1. Correctness — does it fully solve the original issue?
2. Edge cases — are there inputs that would break it?
3. Style — is the code idiomatic for its language?
4. Tests — what tests should accompany this change?

Produce a review summary and a confidence score from 0 to 10.
"""
