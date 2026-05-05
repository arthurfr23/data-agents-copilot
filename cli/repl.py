"""cli.repl — REPL conversacional sem menu. Executa tarefa e retorna ao prompt."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

console = Console()

_MAX_HISTORY_CHARS = 12_000


def _format_history(history: list[dict]) -> str:
    if not history:
        return ""
    parts = ["## Histórico da conversa atual"]
    for h in history:
        role = "Usuário" if h["role"] == "user" else "Agente"
        parts.append(f"**{role}:** {h['content'][:3000]}")
    return "\n\n".join(parts)


def _trim_history(history: list[dict]) -> None:
    """Remove turnos antigos até o total ficar abaixo do limite."""
    while history and sum(len(t["content"]) for t in history) > _MAX_HISTORY_CHARS:
        history.pop(0)


def run_repl(supervisor) -> None:
    """REPL mode: prompt simples, sem menu, com continuação de conversa."""
    from hooks import audit_hook, cost_guard_hook, security_hook

    console.print("[dim]data-agent › /menu para o menu completo · Ctrl+C para sair[/dim]\n")

    conversation_history: list[dict] = []

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
            conversation_history.clear()
            continue

        task_input = line

        ok, reason = security_hook.check_input(task_input)
        if not ok:
            console.print(f"[red]Bloqueado:[/red] {reason}")
            continue

        history_ctx = _format_history(conversation_history)

        with console.status("[bold green]Processando...[/bold green]"):
            result = supervisor.route(task_input, history=history_ctx)

        # cost_guard e audit já são chamados em supervisor._post_process — não duplicar

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

        # Acumular histórico para continuidade entre turnos
        conversation_history.append({"role": "user", "content": task_input})
        conversation_history.append({"role": "assistant", "content": result.content})
        _trim_history(conversation_history)
