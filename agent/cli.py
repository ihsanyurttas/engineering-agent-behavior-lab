"""
agent/cli.py — Typer-based CLI entrypoint.

Commands:
  agent run          Execute the engineering workflow
  agent list-tasks   List available tasks from tasks/issues.yaml
  agent doctor       Validate environment and configuration

Task sources for `agent run` (mutually exclusive):
  --task <id>        Built-in task from tasks/issues.yaml
  --repo + --issue   Ad-hoc task defined inline
  --task-file <path> Task loaded from a YAML file
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="agent",
    help="strands-multi-engineer-agent — multi-provider engineering assistant",
    no_args_is_help=True,
)
console = Console()


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
@app.command()
def run(
    task_id: Optional[str] = typer.Option(
        None,
        "--task",
        "-t",
        help="Task ID from tasks/issues.yaml.",
    ),
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Repo path for an ad-hoc task (requires --issue).",
    ),
    issue: Optional[str] = typer.Option(
        None,
        "--issue",
        help="Issue description for an ad-hoc task (requires --repo).",
    ),
    difficulty: str = typer.Option(
        "medium",
        "--difficulty",
        help="Difficulty label for ad-hoc tasks: easy | medium | hard.",
    ),
    task_file: Optional[Path] = typer.Option(
        None,
        "--task-file",
        help="Path to a YAML file defining a custom task.",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="Override DEFAULT_PROVIDER for this run (anthropic | openai | ollama).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate config and print the task without executing the workflow.",
    ),
) -> None:
    """Run the engineering workflow against a task."""
    import os
    from agent.config import load_config

    # Allow provider override via CLI flag
    if provider:
        os.environ["DEFAULT_PROVIDER"] = provider

    try:
        config = load_config()
    except Exception as exc:
        console.print(f"[bold red]Config error:[/bold red] {exc}")
        console.print("Run [bold]agent doctor[/bold] for a full diagnostic.")
        raise typer.Exit(code=1)

    _configure_logging(config.log_level)

    task = _resolve_task(task_id, repo, issue, difficulty, task_file)
    if task is None:
        raise typer.Exit(code=1)

    console.print(f"\n[bold]Provider:[/bold]  {config.active_provider.value}")
    console.print(f"[bold]Model:[/bold]     {config.active_model()}")
    console.print(f"[bold]Task:[/bold]      {task['id']} — {task['title']}")
    console.print(f"[bold]Repo:[/bold]      {task.get('repo', 'N/A')}\n")

    if dry_run:
        console.print("[yellow]Dry run — skipping workflow execution.[/yellow]")
        return

    # Fail fast: validate model before starting the workflow.
    from providers.base_provider import validate_active_model, ModelValidationError
    try:
        validate_active_model(config)
    except ModelValidationError as exc:
        console.print(f"[bold red]Model validation failed:[/bold red] {exc}")
        raise typer.Exit(code=1)

    from agent.workflow import run_workflow
    from eval.metrics import record_result

    repo_path = task.get("repo", config.sample_repo_path)

    with console.status("[bold green]Running workflow…[/bold green]"):
        try:
            result = run_workflow(
                issue=task["description"],
                repo_path=repo_path,
                config=config,
            )
        except Exception as exc:
            console.print(f"[bold red]Workflow error:[/bold red] {exc}")
            raise typer.Exit(code=1)

    output_path = record_result(result, results_dir=config.results_dir)

    # Summary table
    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column(style="dim")
    summary.add_column(style="bold")

    tokens_in = result.total_input_tokens
    tokens_out = result.total_output_tokens
    token_str = (
        f"{tokens_in:,} in / {tokens_out:,} out"
        if tokens_in is not None
        else "n/a"
    )

    summary.add_row("Provider",   result.provider)
    summary.add_row("Model",      result.model)
    summary.add_row("Latency",    f"{result.total_elapsed_seconds}s")
    summary.add_row("Tool calls", str(result.total_tool_calls) if result.total_tool_calls else "n/a")
    summary.add_row("Tokens",     token_str)

    console.print()
    console.print(summary)
    console.print(f"\n[bold green]Done![/bold green] Results saved to: {output_path}")


# ---------------------------------------------------------------------------
# list-tasks
# ---------------------------------------------------------------------------
@app.command("list-tasks")
def list_tasks() -> None:
    """List all available engineering tasks."""
    from tasks.task_runner import load_tasks

    tasks = load_tasks()
    if not tasks:
        console.print("[yellow]No tasks found in tasks/issues.yaml[/yellow]")
        return

    table = Table(title="Available Tasks", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Repo", style="dim")
    table.add_column("Difficulty", justify="center")

    for task in tasks:
        table.add_row(
            task.get("id", "—"),
            task.get("title", "—"),
            task.get("repo", "—"),
            task.get("difficulty", "—"),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------
@app.command()
def doctor() -> None:
    """Validate environment configuration and provider connectivity."""
    from agent.config import load_config

    console.print("\n[bold]strands-multi-engineer-agent — environment check[/bold]\n")

    # Config validation
    try:
        config = load_config()
        report = config.doctor_report()
        console.print("[bold green]✓[/bold green]  Config loaded successfully\n")
    except Exception as exc:
        console.print(f"[bold red]✗  Config validation failed:[/bold red] {exc}\n")
        raise typer.Exit(code=1)

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    for key, value in report.items():
        style = "red" if value == "NOT SET" else "green" if value == "set" else ""
        table.add_row(key, f"[{style}]{value}[/{style}]" if style else value)

    console.print(table)

    # Strands import check
    try:
        import strands  # noqa: F401
        console.print("\n[green]✓[/green]  strands-agents is importable")
    except ImportError:
        console.print("\n[red]✗[/red]  strands-agents is NOT installed — run: pip install strands-agents")

    # Preflight check — catches wrong model names and auth failures, not a full runtime guarantee
    from providers.base_provider import validate_active_model, ModelValidationError, ProviderImportError
    try:
        validate_active_model(config)
        console.print(f"[green]✓[/green]  Model '{config.active_model()}' is available on {config.active_provider.value}")
    except ModelValidationError as exc:
        console.print(f"[red]✗[/red]  {exc}")
    except ProviderImportError as exc:
        console.print(f"[yellow]⚠[/yellow]  Provider not installed — preflight check skipped: {exc}")

    console.print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _resolve_task(
    task_id: Optional[str],
    repo: Optional[str],
    issue: Optional[str],
    difficulty: str,
    task_file: Optional[Path],
) -> Optional[dict]:
    """
    Resolve a task from one of three sources (mutually exclusive):
      1. --task <id>         → built-in task from issues.yaml
      2. --repo + --issue    → ad-hoc task constructed inline
      3. --task-file <path>  → task loaded from a YAML file

    Returns a task dict on success, None (after printing an error) on failure.
    """
    sources = sum([bool(task_id), bool(repo or issue), bool(task_file)])
    if sources > 1:
        console.print("[red]Error:[/red] only one of --task, --repo/--issue, or --task-file may be used at a time.")
        return None

    # --- Source 1: built-in task ---
    if task_id or (not repo and not issue and not task_file):
        from tasks.task_runner import load_tasks
        tasks = load_tasks()
        if not tasks:
            console.print("[yellow]No tasks found in tasks/issues.yaml[/yellow]")
            return None
        if task_id is None:
            return tasks[0]
        task = next((t for t in tasks if t.get("id") == task_id), None)
        if task is None:
            console.print(f"[red]Task '{task_id}' not found in tasks/issues.yaml.[/red]")
        return task

    # --- Source 2: ad-hoc task ---
    if repo or issue:
        if not repo or not issue:
            console.print("[red]Error:[/red] --repo and --issue must be used together.")
            return None
        return {
            "id": "adhoc",
            "title": issue[:72],
            "description": issue,
            "repo": repo,
            "difficulty": difficulty,
        }

    # --- Source 3: task file ---
    if task_file:
        from tasks.task_runner import task_from_file
        try:
            return task_from_file(task_file)
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            return None

    return None  # unreachable


if __name__ == "__main__":
    app()
