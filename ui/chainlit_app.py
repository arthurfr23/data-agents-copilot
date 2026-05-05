"""Chainlit UI — interface web do data-agents-copilot."""

import asyncio

import chainlit as cl

from agents.supervisor import Supervisor
from config.settings import settings
from hooks import audit_hook, cost_guard_hook, security_hook
from orchestrator.qa_orchestrator import QAOrchestrator, should_bypass

_MAX_HISTORY_CHARS = 12_000

_HELP = """\
**data-agents-copilot** — comandos disponíveis:

| Comando | Agente | Uso |
|---|---|---|
| `/plan <tarefa>` | Supervisor | Tarefas complexas com PRD |
| `/spark <tarefa>` | Spark Expert | PySpark, Delta Lake, DLT |
| `/sql <tarefa>` | SQL Expert | Queries, modelagem, Unity Catalog |
| `/pipeline <tarefa>` | Pipeline Architect | ETL/ELT com execução |
| `/quality <tarefa>` | Data Quality | Validação, DQX, profiling |
| `/naming <tarefa>` | Naming Guard | Auditoria de nomenclatura |
| `/governance <tarefa>` | Governance Auditor | PII, LGPD, controles de acesso |
| `/dbt <tarefa>` | dbt Expert | Models, snapshots, incremental |
| `/python <tarefa>` | Python Expert | Código Python, testes |
| `/fabric <tarefa>` | Fabric Expert | Lakehouse, OneLake, Direct Lake |
| `/lakehouse <tarefa>` | Lakehouse Engineer | Implantação, migração, sustentação |
| `/ops <tarefa>` | Lakehouse Engineer | Manutenção, incidente, custo |
| `/ai <tarefa>` | Databricks AI | Agent Bricks, Genie, MLflow |
| `/assessment` | fabricgov + Governance Auditor | Assessment completo de governança Fabric |
| `/devops <tarefa>` | DevOps Engineer | DABs, Azure DevOps, Fabric CI/CD |
| `/geral <pergunta>` | Geral | Conceitual, sem MCP |
| `/review <artefato>` | Supervisor | Review de código/pipeline |
| `/party <tarefa>` | Party Mode | Múlti-agente em paralelo |
| `/health` | — | Status dos agentes |
| `/help` | — | Este menu |
"""


def _format_history(history: list[dict]) -> str:
    if not history:
        return ""
    parts = ["## Histórico da conversa atual"]
    for h in history:
        role = "Usuário" if h["role"] == "user" else "Agente"
        parts.append(f"**{role}:** {h['content'][:3000]}")
    return "\n\n".join(parts)


def _trim_history(history: list[dict]) -> None:
    while history and sum(len(t["content"]) for t in history) > _MAX_HISTORY_CHARS:
        history.pop(0)


@cl.on_chat_start
async def on_start():
    supervisor = Supervisor()
    qa_agent = supervisor.get_agent("qa_reviewer")
    qa_orchestrator = (
        QAOrchestrator(
            supervisor,
            qa_agent,
            max_rounds=settings.qa_max_rounds,
            pass_threshold=settings.qa_score_threshold,
        )
        if settings.qa_enabled and qa_agent
        else None
    )
    cl.user_session.set("supervisor", supervisor)
    cl.user_session.set("qa_orchestrator", qa_orchestrator)
    cl.user_session.set("conversation_history", [])
    await cl.Message(content=_HELP).send()


@cl.on_message
async def on_message(message: cl.Message):
    supervisor: Supervisor | None = cl.user_session.get("supervisor")
    if supervisor is None:
        await cl.Message(content="Aguarde — inicializando agentes...").send()
        return

    user_input = message.content.strip()

    if user_input.lower() in ("/help", "help", "ajuda"):
        await cl.Message(content=_HELP).send()
        return

    allowed, reason = security_hook.check(user_input)
    if not allowed:
        await cl.Message(content=f"Bloqueado pelo hook de segurança: {reason}").send()
        return

    conversation_history: list[dict] = cl.user_session.get("conversation_history", [])
    history_ctx = _format_history(conversation_history)

    loop = asyncio.get_running_loop()

    qa_orchestrator: QAOrchestrator | None = cl.user_session.get("qa_orchestrator")

    if qa_orchestrator and not should_bypass(user_input):
        async with cl.Step(name="📋 Negociando Spec") as step:
            spec, rounds, _neg_tok, _neg_calls = await loop.run_in_executor(
                None, qa_orchestrator.negotiate_spec, user_input
            )
            step.output = f"v{spec.version} — {rounds} round(s) | agente: {spec.agent_name}"

        async with cl.Step(name="🤖 Executando") as step:
            delivery = await loop.run_in_executor(
                None, qa_orchestrator.execute, user_input, spec, history_ctx
            )
            step.output = f"Tokens: {delivery.tokens_used}"

        async with cl.Step(name="✅ Verificando Qualidade") as step:
            report, _ver_tok, _ver_calls = await loop.run_in_executor(
                None, qa_orchestrator.verify, spec, delivery
            )
            icon = "✅" if report.passed else "❌"
            step.output = f"{icon} Score: {report.score:.0%}"
        audit_hook.record(
            agent="qa_orchestrator",
            task=user_input,
            tokens_used=delivery.tokens_used,
            tool_calls=delivery.tool_calls_count,
        )
        cost_guard_hook.track("qa_orchestrator", delivery.tokens_used, session_id=cl.user_session.get("id", "default"))

        score_block = "\n\n---\n\n" + report.summary(settings.qa_score_threshold)
        content = delivery.content + score_block
        await cl.Message(content=content).send()

        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({"role": "assistant", "content": content})
    else:
        async with cl.Step(name="Processando") as step:
            step.input = user_input
            result = await loop.run_in_executor(
                None, supervisor.route, user_input, history_ctx
            )

            audit_hook.record(
                agent="supervisor_route",
                task=user_input,
                tokens_used=result.tokens_used,
                tool_calls=result.tool_calls_count,
            )
            # cost_guard já é chamado em supervisor._post_process — só lê o summary aqui
            sid = cl.user_session.get("id", "default")
            summary = cost_guard_hook.session_summary(session_id=sid)
            step.output = (
                f"Tokens: {result.tokens_used} | "
                f"Total sessão: {summary['total_tokens']} "
                f"({summary['budget_pct']}% budget)"
            )

        await cl.Message(content=result.content).send()

        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({"role": "assistant", "content": result.content})

    _trim_history(conversation_history)
    cl.user_session.set("conversation_history", conversation_history)
