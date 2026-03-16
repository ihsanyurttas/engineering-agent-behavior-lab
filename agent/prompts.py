"""
agent/prompts.py — prompt templates for each workflow phase.

Each function has two variants selected by the `concise` flag:
  concise=True  (minimal mode)  — short, structured, relies on conversation
                                   history. Low token usage.
  concise=False (standard mode) — full context re-injected per phase.
                                   Higher token usage, more self-contained output.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

# Minimal: ~15 tokens. Sent on every agent call — savings multiply.
SYSTEM_PROMPT_MINIMAL = """\
You are a software engineer. Inspect repos, plan changes, implement, and \
check your work. Be precise and concise.\
"""

# Standard: fuller persona and rules for richer output.
SYSTEM_PROMPT_STANDARD = """\
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


def system_prompt(*, concise: bool = True) -> str:
    return SYSTEM_PROMPT_MINIMAL if concise else SYSTEM_PROMPT_STANDARD


# ---------------------------------------------------------------------------
# Phase prompts
# ---------------------------------------------------------------------------

def inspect_prompt(issue: str, repo_path: str, *, concise: bool = True) -> str:
    if concise:
        # Structured output format constrains response length.
        # "what the repo does" question is dropped — we only need actionable facts.
        return f"""\
## Inspect

Issue: {issue}
Repo: {repo_path}

Use list_files then read the relevant files.
Reply in this format only — no extra prose:

relevant_files: <comma-separated list>
root_cause: <one sentence>
"""
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


def plan_prompt(
    issue: str,
    inspection_summary: str,
    *,
    concise: bool = True,
) -> str:
    if concise:
        # Issue and inspection are already in conversation history.
        # No re-injection needed — saves inspection_summary input tokens.
        return """\
## Plan

List numbered steps to fix the issue. One line per step, no explanations.
"""
    return f"""\
## Phase 2: Implementation Plan

Issue:
{issue}

Inspection findings:
{inspection_summary}

Produce a numbered step-by-step implementation plan.
Be specific about which files to change and what changes to make.
"""


def implement_prompt(
    issue: str,
    inspection: str,
    plan: str,
    *,
    concise: bool = True,
) -> str:
    if concise:
        # Issue, inspection, and plan are all in conversation history.
        # This prompt is intentionally minimal — it just triggers execution.
        return """\
## Implement

Execute the plan. Write complete replacement content for each file you change.
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


def self_review_prompt(
    issue: str,
    implementation: str,
    *,
    concise: bool = True,
) -> str:
    if concise:
        # Implementation is in conversation history — no re-injection.
        # Risk check replaces narrative review: 3 bullets + score.
        return """\
## Risk Check

List up to 3 risks or gaps in your implementation. One line each.
End with: Confidence: X/10
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
