# Engineering Agent Behavior Lab

Most evaluations focus on what AI agents *can do*.

This repo focuses on how they *behave*.

Given the same engineering workflow and the same task, different models produce different:
- decisions
- execution strategies
- failure patterns

In real systems, these differences are not cosmetic.  
They directly impact reliability, debugging, and operational risk.

This project is a controlled environment to observe and compare agent behavior under identical conditions.

## Why this matters

Most engineering teams treat AI agents as interchangeable.

They are not.

Even when agents follow the same workflow, their behavior differs in:
- how they interpret tasks
- how they prioritize actions
- how they handle uncertainty and errors
- how they recover from failure

These differences create hidden risks:
- inconsistent outcomes
- hard-to-debug failures
- unpredictable system behavior

If we want reliable AI-assisted engineering systems, we need to understand behavior — not just capability.

## Same workflow. Same task. Same tools. Different behavior.

Most LLM benchmarks measure models in isolation.

This shows what actually happens inside a real engineering agent workflow.

The same task is executed across providers:
Claude, GPT-4o, and Llama 3.2.

Same inputs. Same system.

Different behavior.

- Some models are fast and decisive
- Some overthink and self-review heavily
- Some take 6x longer for the same outcome
- Some fail silently with no output or clear signal

That difference matters.

In agent systems, reliability matters more than raw capability.

Built on [AWS Strands](https://github.com/strands-agents/sdk-python). Swap the provider with one env var.

---

Not a production engineering agent.

A controlled experiment:
fixed workflow, fixed task, variable provider.

The goal is behavioral comparison — not building the best agent.

---

## Benchmark Output

After each run the agent prints a compact summary:

```
  Provider    openai
  Model       gpt-4o-mini
  Latency     38.5s
  Tool calls  16
  Tokens      4,821 in / 612 out

Done! Results saved to: eval/results/openai_gpt-4o-mini_20260316T163403Z.json
```

The full result is also written as a structured JSON file in `eval/results/`:

```
eval/results/
  anthropic_claude-sonnet-4-6_20260316T130602Z.json
  openai_gpt-4o-mini_20260316T155350Z.json
  ollama_llama3_20260316T161200Z.json
```

Every file captures the full run for one provider:

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "total_elapsed_seconds": 51.87,
  "total_input_tokens": 4821,
  "total_output_tokens": 612,
  "confidence_score": 7.0,
  "phases": [
    { "phase": "inspect",     "elapsed_seconds": 8.46,  "input_tokens": null, "output_tokens": null },
    { "phase": "plan",        "elapsed_seconds": 3.85,  "input_tokens": null, "output_tokens": null },
    { "phase": "implement",   "elapsed_seconds": 36.55, "input_tokens": null, "output_tokens": null },
    { "phase": "self_review", "elapsed_seconds": 3.02,  "input_tokens": null, "output_tokens": null }
  ]
}
```

Run the same task across all three providers and compare the result files side by side
to see where they differ in speed, cost, and output quality.

Because every provider run produces the same schema, results can be compared programmatically across models and providers.

---

## Architecture

```
strands-multi-engineer-agent/
├── agent/
│   ├── cli.py          # Typer CLI: run / list-tasks / doctor
│   ├── config.py       # Env-var validation + typed config (Pydantic)
│   ├── prompts.py      # Prompt templates per workflow phase
│   └── workflow.py     # Strands agent orchestration loop
├── providers/
│   ├── base_provider.py     # Abstract base + factory (get_strands_model)
│   └── provider_config.py   # Per-provider requirements documentation
├── tools/
│   ├── repo_reader.py   # list_files, read_file  (@tool)
│   ├── search_tools.py  # search_in_repo         (@tool)
│   ├── patch_writer.py  # write_file             (@tool, sandboxed)
│   └── test_runner.py   # run_tests              (@tool)
├── tasks/
│   ├── issues.yaml      # Sample engineering tasks
│   └── task_runner.py   # Load + dispatch tasks
├── eval/
│   ├── metrics.py       # Record + compare run results
│   ├── result_schema.py # Pydantic schema for WorkflowResult
│   └── results/         # JSON output per provider run (gitignored)
├── sample_repos/
│   ├── tiny_fastapi_app/   # Python target with deliberate gaps
│   └── tiny_node_service/  # Node.js target with deliberate gaps
└── content/
    └── medium_notes.md  # Notes
```

### Workflow phases

```
Issue description
       │
       ▼
  ┌─────────────┐
  │  1. Inspect  │  read_file, list_files, search_in_repo
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  2. Plan     │  (reasoning only, no tools)
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  3. Implement│  write_file
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  4. Review   │  self_review (risks + confidence score)
  └──────┬──────┘
         │
         ▼
  WorkflowResult (JSON)
```

### Provider abstraction

```python
# providers/base_provider.py
model = get_strands_model(config)   # ← only call the workflow needs

# The factory returns a Strands-compatible model object
# configured from environment variables, regardless of provider.
```

---

## Portability Principles

1. **Secrets from env vars only** — no hardcoded keys anywhere
2. **Container-friendly by default** — Ollama runs as a Docker Compose service; no host binary assumed
3. **Reproducible setup** — `make setup` bootstraps a clean `venv` from scratch
4. **Explicit runtime selection** — `AGENT_RUNTIME=local|docker`
5. **Provider-agnostic workflow** — `workflow.py` never imports a provider directly

---

## Tasks

Tasks are defined in `tasks/issues.yaml`. Each task is a self-contained engineering problem
run against a sample repository:

```yaml
- id: fastapi-missing-validation
  repo: sample_repos/tiny_fastapi_app
  description: Add Pydantic model validation to the POST /items endpoint
  difficulty: easy
```

Run with: `venv/bin/agent run --task fastapi-missing-validation`

---

## Supported Providers

| Provider | Env vars required | Notes |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | Uses Strands Anthropic model. |
| `openai` | `OPENAI_API_KEY` | Uses Strands OpenAI model. |
| `ollama` | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | No API key. Runs locally via Docker Compose or native install. |

> For low-cost experimentation, start with `gpt-4o-mini` or Ollama.
> Hosted providers incur real API cost. Use `WORKFLOW_MODE=minimal` for cheaper runs.

---

## Setup

```bash
git clone <repo-url>
cd strands-multi-engineer-agent
make setup                # creates venv, copies .env.example → .env, installs deps
# edit .env — set your API key and DEFAULT_PROVIDER
make doctor               # validate config
make run                  # run with DEFAULT_PROVIDER (or: venv/bin/agent run --task ...)
```

**Anthropic:** set `ANTHROPIC_API_KEY` in `.env`
**OpenAI:** set `OPENAI_API_KEY` in `.env`
**Ollama (Docker Compose):**
```bash
make ollama-up            # start container, wait for healthy
make ollama-pull          # pull llama3.2  (MODEL=mistral to override)
make ollama-run           # run agent via Compose
```
**Ollama (native):** set `OLLAMA_BASE_URL=http://localhost:11434` in `.env`, then `make run`

---

## Custom Tasks

Built-in tasks require editing `tasks/issues.yaml`. Two shortcuts skip that:

**Ad-hoc task — define inline:**
```bash
venv/bin/agent run \
  --repo sample_repos/tiny_fastapi_app \
  --issue "Add pagination support to GET /items" \
  --difficulty medium
```

**Task file — provide a YAML file:**
```bash
venv/bin/agent run --task-file my_task.yaml
```

```yaml
# my_task.yaml
id: add-pagination
repo: sample_repos/tiny_fastapi_app
description: Add pagination support to GET /items
difficulty: medium
```

Required fields: `repo`, `description`. All other fields are optional.
Only one task source may be used at a time: `--task`, `--repo/--issue`, or `--task-file`.

---

## Environment Variables

All configuration comes from environment variables. Copy `.env.example` to `.env` and fill in values.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DEFAULT_PROVIDER` | No | `anthropic` | Active provider: `anthropic` \| `openai` \| `ollama` |
| `ANTHROPIC_API_KEY` | If using Anthropic | — | Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-6` | Anthropic model ID |
| `ANTHROPIC_MAX_TOKENS` | No | `4096` | Max output tokens for Anthropic |
| `OPENAI_API_KEY` | If using OpenAI | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model ID |
| `OLLAMA_BASE_URL` | If using Ollama | `http://ollama:11434` | Ollama server URL (`http://localhost:11434` for native) |
| `OLLAMA_MODEL` | If using Ollama | `llama3.2` | Ollama model name — must support tool calling |
| `AGENT_RUNTIME` | No | `local` | `local` \| `docker` |
| `WORKFLOW_MODE` | No | `minimal` | `minimal` (low cost) \| `standard` (full context per phase) |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `MAX_ITERATIONS` | No | `10` | Max Strands tool-use iterations per phase |
| `RESULTS_DIR` | No | `eval/results` | Where to write JSON result files |

---

## Testing

Before each benchmark run the agent performs a provider preflight check —
a lightweight metadata call that catches wrong model names and auth failures
before the workflow starts. This prevents a misconfigured environment from
silently producing a failed or incomplete benchmark result.

The preflight check is exercised by a mocked unit test suite that runs
without API keys or network access:

```bash
make test   # ~1 second, no .env required
```

> The preflight check is not a full runtime guarantee. It does not verify
> tool-calling support or endpoint-level behaviour — only that the model ID
> is known and credentials are accepted.

---

## Makefile Targets

```
make setup            Bootstrap: create venv, copy .env, install deps
make setup-compose    Bootstrap + Docker/Docker Compose checks
make install          Re-install deps into venv (pip or uv)

make doctor           Validate environment and config
make list-tasks       List available tasks
make run              Run agent workflow (DEFAULT_PROVIDER)

make ollama-up        Start Ollama container (Docker Compose)
make ollama-pull      Pull a model  [MODEL=llama3.2]
make ollama-run       Run agent against Ollama via Docker Compose

make compose-up       Build agent image + start all services
make compose-down     Stop all services
make compose-logs     Tail Ollama container logs

make lint             Run ruff linter
make format           Run ruff formatter
make typecheck        Run mypy
make test             Run pytest
make clean            Remove build artifacts
```

---

## Kubernetes (Planned runtime)

Not yet implemented. The architecture is designed to support it:

- All config via env vars → easy ConfigMap / Secret mapping
- Docker image is minimal and non-root
- Ollama can be deployed as a Deployment + Service
- Results directory can be mounted as a PersistentVolumeClaim
- No host-path assumptions anywhere

---

## Project Status

| Phase | Status |
|---|---|
| Phase 1: Skeleton + architecture | ✅ Complete |
| Phase 2: Anthropic workflow (end-to-end) | ✅ Complete |
| Phase 3: OpenAI + Ollama providers | ✅ Complete |
| Phase 4: Eval metrics + comparison | 🔲 Planned |

---

## License

MIT
