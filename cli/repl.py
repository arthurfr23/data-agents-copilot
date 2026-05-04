"""cli.repl — REPL conversacional sem menu. Executa tarefa e retorna ao prompt."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

console = Console()

_QUESTION_ENDINGS = ("?", "confirma", "confirmas", "confirme", "prosseguir", "prossigo")


def _looks_like_question(text: str) -> bool:
    last = text.rstrip().rsplit("\n", 1)[-1].lower().rstrip()
    return any(last.endswith(e) for e in _QUESTION_ENDINGS)


def run_repl(supervisor) -> None:
    """REPL mode: prompt simples, sem menu, com continuação de conversa."""
    from hooks import audit_hook, cost_guard_hook, security_hook

    console.print("[dim]data-agent › /menu para o menu completo · Ctrl+C para sair[/dim]\n")

    pending_context: str | None = None  # guarda output anterior quando agente fez pergunta

    while True:
        try:
            line = input("〉 ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Até logo![/dim]")
            break

        if not line:
            continue

        if line in ("/exit", "exit", "quit", "sair"):
            console.print("[dim]Até logo![/dim]")
            break

        if line in ("/menu", "menu"):
            from cli.menu import run_menu
            run_menu(supervisor)
            pending_context = None
            continue

        # Se há contexto pendente (agente fez pergunta), injetar como resposta
        if pending_context is not None:
            task_input = f"/resume {line}"
            pending_context = None
        else:
            task_input = line

        ok, reason = security_hook.check_input(task_input)
        if not ok:
            console.print(f"[red]Bloqueado:[/red] {reason}")
            continue

        with console.status("[bold green]Processando...[/bold green]"):
            result = supervisor.route(task_input)

        audit_hook.record("repl", task_input, result.tokens_used, result.tool_calls_count)
        cost_guard_hook.track("general", result.tokens_used)

        console.print(Markdown(result.content))

        summary = cost_guard_hook.session_summary()
        console.print(
            f"[dim]tokens: {result.tokens_used} | "
            f"sessão: {summary['total_tokens']} ({summary['budget_pct']}% budget)[/dim]\n"
        )

        # Persistir resultado em output/sessions/
        sessions_dir = Path("output/sessions")
        sessions_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        (sessions_dir / f"{ts}.md").write_text(
            f"# {task_input}\n\n{result.content}\n", encoding="utf-8"
        )
        console.print(f"[dim]Sessão salva em output/sessions/{ts}.md[/dim]")

        # Se o agente fez uma pergunta, manter contexto para a próxima entrada
        if _looks_like_question(result.content):
            pending_context = result.content
