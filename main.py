"""CLI entry point — modo interativo e single-query."""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

load_dotenv()

from agents.supervisor import Supervisor  # noqa: E402 — após load_dotenv
from config.settings import settings  # noqa: E402
from hooks import audit_hook, cost_guard_hook, security_hook  # noqa: E402

console = Console()
logging.basicConfig(level=getattr(logging, settings.console_log_level))

_COMMANDS_HINT = (
    "[dim]/plan /spark /sql /pipeline /quality /geral /review — /help para lista completa[/dim]"
)


def _print_diagnostics():
    d = settings.diagnostics()
    status = " | ".join(f"{k}: {'✓' if v else '✗'}" for k, v in d.items())
    console.print(Panel(status, title="arthur-data-agents", expand=False))


def _process(user_input: str, supervisor: Supervisor) -> None:
    allowed, reason = security_hook.check(user_input)
    if not allowed:
        console.print(f"[red]Bloqueado:[/red] {reason}")
        return

    with console.status("[bold green]Processando..."):
        result = supervisor.route(user_input)

    audit_hook.record(
        agent="cli",
        task=user_input,
        tokens_used=result.tokens_used,
        tool_calls=result.tool_calls_count,
    )
    cost_guard_hook.track("general", result.tokens_used)

    console.print(Markdown(result.content))
    summary = cost_guard_hook.session_summary()
    console.print(
        f"[dim]tokens: {result.tokens_used} | sessão: {summary['total_tokens']} "
        f"({summary['budget_pct']}% budget)[/dim]"
    )


def main():
    supervisor = Supervisor()

    # Modo single-query: python main.py "tarefa aqui"
    if len(sys.argv) > 1:
        _print_diagnostics()
        _process(" ".join(sys.argv[1:]), supervisor)
        return

    # Modo interativo
    _print_diagnostics()
    console.print(_COMMANDS_HINT)

    while True:
        try:
            user_input = console.input("\n[bold cyan]>[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Saindo...[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
            break
        if user_input.lower() in ("/help", "help"):
            console.print(_COMMANDS_HINT)
            continue

        _process(user_input, supervisor)


if __name__ == "__main__":
    main()
