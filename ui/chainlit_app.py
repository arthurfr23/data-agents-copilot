"""Chainlit UI — interface web do arthur-data-agents."""

import chainlit as cl

from agents.supervisor import Supervisor
from hooks import audit_hook, cost_guard_hook, security_hook

supervisor = Supervisor()

_HELP = """\
**arthur-data-agents** — comandos disponíveis:

| Comando | Agente | Uso |
|---|---|---|
| `/plan <tarefa>` | Supervisor | Tarefas complexas com PRD |
| `/spark <tarefa>` | Spark Expert | PySpark, Delta Lake, DLT |
| `/sql <tarefa>` | SQL Expert | Queries, modelagem, Unity Catalog |
| `/pipeline <tarefa>` | Pipeline Architect | ETL/ELT com execução |
| `/quality <tarefa>` | Data Quality | Validação, DQX, profiling |
| `/geral <pergunta>` | Geral | Conceitual, sem MCP |
| `/review <artefato>` | Supervisor | Review de código/pipeline |
| `/help` | — | Este menu |
"""


@cl.on_chat_start
async def on_start():
    diag = supervisor._supervisor_agent.config  # noqa: SLF001 — acesso intencional
    await cl.Message(content=_HELP).send()


@cl.on_message
async def on_message(message: cl.Message):
    user_input = message.content.strip()

    if user_input.lower() in ("/help", "help", "ajuda"):
        await cl.Message(content=_HELP).send()
        return

    # Checagem de segurança
    allowed, reason = security_hook.check(user_input)
    if not allowed:
        await cl.Message(content=f"Bloqueado pelo hook de segurança: {reason}").send()
        return

    async with cl.Step(name="Processando") as step:
        step.input = user_input
        result = supervisor.route(user_input)

        audit_hook.record(
            agent="supervisor_route",
            task=user_input,
            tokens_used=result.tokens_used,
            tool_calls=result.tool_calls_count,
        )
        cost_guard_hook.track("general", result.tokens_used)

        summary = cost_guard_hook.session_summary()
        step.output = f"Tokens: {result.tokens_used} | Total sessão: {summary['total_tokens']} ({summary['budget_pct']}% budget)"

    await cl.Message(content=result.content).send()
