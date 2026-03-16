# strands-multi-engineer-agent

A portable, multi-model engineering agent built on [AWS Strands](https://github.com/strands-agents/sdk-python).

The same 4-phase workflow — **inspect → plan → implement → review** — runs identically
across OpenAI, Anthropic, and Ollama. Swap the provider with one env var. Compare results.

> Built as a public proof-of-concept and the basis for a Medium article.

---

## Goal

Run the same engineering workflow across different model providers and compare:

- **Quality** — does the generated code actually solve the issue?
- **Latency** — how long does each phase take?
- **Cost** — input/output token counts and estimated cost
- **Tool-calling behaviour** — how many tool calls, what patterns?
- **Local vs hosted** — Ollama vs cloud APIs

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
│   ├── patch_writer.py  # write_patch            (@tool, sandboxed)
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
    └── medium_notes.md  # Article notes
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
  │  3. Implement│  write_patch
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  4. Review   │  run_tests
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
3. **Reproducible setup** — `make setup` bootstraps a clean `.venv` from scratch
4. **Explicit runtime selection** — `AGENT_RUNTIME=local|docker|kubernetes`
5. **Provider-agnostic workflow** — `workflow.py` never imports a provider directly

---

## Supported Providers

| Provider | Env vars required | Notes |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | Default. Uses Strands Anthropic model. |
| `openai` | `OPENAI_API_KEY` | Uses Strands OpenAI model. |
| `ollama` | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | No API key. Recommended via Docker Compose. |

---

## Local Setup (native Python)

**Requirements:** Python 3.11+

```bash
# 1. Clone
git clone <repo-url>
cd strands-multi-engineer-agent

# 2. Bootstrap (creates .venv, copies .env.example → .env, installs deps)
make setup

# 3. Activate the virtual environment
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 4. Edit .env with your API keys
#    At minimum set ANTHROPIC_API_KEY (default provider is anthropic)

# 5. Validate your setup
agent doctor

# 6. List available tasks
agent list-tasks

# 7. Run the workflow
agent run
agent run --task fastapi-missing-validation
agent run --provider openai --task fastapi-missing-validation
```

---

## Docker Compose Setup (recommended for Ollama)

Docker Compose is the primary path for running Ollama without a host binary install.

```bash
# 1. Copy and edit .env
cp .env.example .env
# edit .env — set your API keys

# 2. Start Ollama (only needed when using the ollama provider)
docker compose up ollama -d

# 3. Wait for Ollama to be healthy, then pull a model
docker compose exec ollama ollama pull llama3

# 4. Run agent commands
docker compose run --rm agent doctor
docker compose run --rm agent list-tasks
docker compose run --rm agent run --provider ollama

# 5. Stop everything
make compose-down
```

The `ollama-models` Docker volume persists downloaded models between restarts.

Generated patches from the implement phase are written into `sample_repos/` and
are visible on the host after each run — the directory is mounted writable.

---

## Environment Variables

All configuration comes from environment variables. Copy `.env.example` to `.env` and fill in values.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DEFAULT_PROVIDER` | No | `anthropic` | Active provider: `anthropic` \| `openai` \| `ollama` |
| `ANTHROPIC_API_KEY` | If using Anthropic | — | Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-6` | Anthropic model ID |
| `OPENAI_API_KEY` | If using OpenAI | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model ID |
| `OLLAMA_BASE_URL` | If using Ollama | `http://ollama:11434` | Ollama service URL |
| `OLLAMA_MODEL` | If using Ollama | `llama3` | Ollama model name |
| `AGENT_RUNTIME` | No | `local` | `local` \| `docker` \| `kubernetes` |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `MAX_ITERATIONS` | No | `10` | Max Strands tool-use iterations per phase |
| `RESULTS_DIR` | No | `eval/results` | Where to write JSON result files |

---

## Makefile Targets

```
make setup          Bootstrap: create .venv, copy .env, install deps
make install        Install deps only (assumes .venv exists)
make lint           Run ruff linter
make format         Run ruff formatter
make typecheck      Run mypy
make test           Run pytest
make run            Run agent workflow (DEFAULT_PROVIDER)
make list-tasks     List available tasks
make doctor         Validate environment
make compose-up     Start services (Docker Compose)
make compose-down   Stop services
make compose-logs   Tail Docker Compose logs
make clean          Remove build artifacts
```

---

## Kubernetes (Future Direction)

The project is designed with Kubernetes compatibility in mind:

- All config via env vars → easy ConfigMap / Secret mapping
- Docker image is minimal and non-root
- Ollama can be deployed as a Deployment + Service
- Results directory can be mounted as a PersistentVolumeClaim
- No host-path assumptions anywhere

Kubernetes manifests will be added in a future phase.

---

## Project Status

| Phase | Status |
|---|---|
| Phase 1: Skeleton + architecture | ✅ Complete |
| Phase 2: Anthropic workflow (end-to-end) | 🔲 Next |
| Phase 3: OpenAI + Ollama providers | 🔲 Planned |
| Phase 4: Eval metrics + comparison | 🔲 Planned |
| Phase 5: Medium article + polish | 🔲 Planned |

---

## License

MIT
