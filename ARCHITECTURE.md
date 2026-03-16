# Architecture

This document describes the four core architectural layers of **strands-multi-engineer-agent**.

---

## 1. Provider Abstraction

The provider layer decouples the workflow from any specific LLM vendor. The workflow only calls one function — `get_strands_model(config)` — and receives a Strands-compatible model object. It never imports a provider directly.

```
agent/config.py          providers/base_provider.py
─────────────────        ──────────────────────────────────────────────
AgentConfig              BaseProviderBuilder  (abstract)
  default_provider  ───►   AnthropicProvider  → AnthropicModel(api_key, model_id)
  anthropic_api_key        OpenAIProvider     → OpenAIModel(api_key, model_id)
  openai_api_key           OllamaProvider     → OllamaModel(host, model_id)
  ollama_base_url                    │
  ollama_model                       ▼
                           get_strands_model(config)   ← only call workflow.py makes
```

All credentials come exclusively from environment variables — never hardcoded. The `AgentConfig` Pydantic model validates required vars at startup and fails with a clear message before the workflow runs.

**Adding a new provider** requires three changes only:
1. Add a value to the `Provider` enum in `agent/config.py`
2. Add a `BaseProviderBuilder` subclass in `providers/base_provider.py`
3. Add required env vars to `.env.example`

The `providers/provider_config.py` module documents which env vars each provider requires and exposes a `check_provider_requirements()` helper used by `agent doctor`.

---

## 2. Workflow Phases

The workflow is a fixed 4-phase sequential loop driven by `agent/workflow.py`. The same loop runs regardless of provider. Each phase sends a prompt to the Strands agent, captures the output, and passes it as context to the next phase.

```
issue + repo_path
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  Phase 1: Inspect                                         │
│  prompt  → inspect_prompt(issue, repo_path)               │
│  tools   → list_files, read_file, search_in_repo          │
│  output  → WorkflowContext.inspection                     │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│  Phase 2: Plan                                            │
│  prompt  → plan_prompt(issue, inspection)                 │
│  tools   → (reasoning only, no tool calls)                │
│  output  → WorkflowContext.plan                           │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│  Phase 3: Implement                                       │
│  prompt  → implement_prompt(plan)                         │
│  tools   → write_patch                                    │
│  output  → WorkflowContext.implementation                 │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│  Phase 4: Review                                          │
│  prompt  → review_prompt(implementation)                  │
│  tools   → run_tests                                      │
│  output  → WorkflowContext.review + confidence_score      │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
                 WorkflowResult (→ eval/results/)
```

**Key design decisions:**

- `max_parallel_tool_uses=1` — tool calls are sequential within a phase. This ensures deterministic, comparable output across providers.
- Each phase produces a `PhaseResult` (prompt, output, elapsed seconds) that is stored in the `WorkflowContext` and included in the final `WorkflowResult`.
- The Strands `Agent` instance is shared across all four phases so the conversation history is preserved — the model has full context when it moves from plan to implementation.
- Prompt templates live in `agent/prompts.py`, separate from orchestration logic, so they can be iterated on independently.

---

## 3. Tool Execution Model

Tools are Python functions decorated with `@tool` from the `strands` package. Strands handles the tool-use loop: it sends the tool schema to the model, receives a tool call, executes the function, and feeds the result back to the model automatically.

```
Strands Agent loop (per phase)
──────────────────────────────────────────────────────────────
prompt
  │
  ▼
model response
  ├─ text only  ──────────────────────────────► output captured
  └─ tool call
       │
       ▼
  tool dispatcher
       ├─ list_files(repo_path, extension?)    read-only
       ├─ read_file(file_path, max_lines?)     read-only, 1 MB guard
       ├─ search_in_repo(repo_path, pattern)   read-only, regex
       ├─ write_patch(file_path, content)      write, sandboxed
       └─ run_tests(repo_path, test_command?)  subprocess, sandboxed
             │
             ▼
       tool result → fed back to model → next model response
             │
       (repeats up to max_iterations)
```

**Safety constraints:**

| Tool | Access | Constraint |
|---|---|---|
| `list_files` | Read | Skips hidden dirs, `__pycache__`, `node_modules` |
| `read_file` | Read | Max 500 lines returned; 1 MB file size guard |
| `search_in_repo` | Read | Regex validated before walking |
| `write_patch` | Write | Path must resolve inside `sample_repos/` — writes elsewhere are rejected |
| `run_tests` | Execute | Process must be inside `sample_repos/`; 60s timeout; captured stdout/stderr only |

All tools return strings — success output or an `ERROR: ...` prefixed message — so the model can reason about failures without the agent crashing.

---

## 4. Evaluation Model

Every provider run produces one `WorkflowResult` serialised to JSON in `eval/results/`. The filename encodes provider, model, and UTC timestamp, making runs independently addressable and trivially comparable.

```
WorkflowResult (eval/result_schema.py)
───────────────────────────────────────────────────────────────
provider                  "anthropic" | "openai" | "ollama"
model                     e.g. "claude-sonnet-4-6"
issue                     the original task description
repo_path                 target repository
run_at                    UTC timestamp

phases: list[PhaseResult]
  └─ phase                "inspect" | "plan" | "implement" | "review"
     prompt               exact prompt sent to the model
     output               full model response text
     elapsed_seconds      wall-clock time for this phase

total_elapsed_seconds     sum across all phases
total_input_tokens        populated when provider exposes usage
total_output_tokens       populated when provider exposes usage
estimated_cost_usd        populated in Phase 4
confidence_score          0–10 extracted from the review phase output
```

**File naming:**

```
eval/results/
  anthropic_claude-sonnet-4-6_20240315T142301Z.json
  openai_gpt-4o_20240315T143512Z.json
  ollama_llama3_20240315T150847Z.json
```

**Comparison API** (`eval/metrics.py`):

```python
from eval.metrics import load_results, compare_results

results = load_results()          # load all JSON files from eval/results/
table   = compare_results(results) # sorted by total_elapsed_seconds
```

`compare_results()` returns a list of `summary()` dicts — one row per run — ready to render as a table or feed into a notebook for further analysis. The schema is intentionally flat so it can be loaded directly into pandas or any CSV tool without transformation.
