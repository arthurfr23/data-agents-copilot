"""Supervisor: coordena roteamento e delegação entre agentes especialistas."""

from __future__ import annotations

import re
from pathlib import Path

from agents.base import AgentResult, BaseAgent
from agents.loader import AGENT_COMMANDS, load_all

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "prd"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_COMPLEX_KEYWORDS = re.compile(
    r"\b(pipeline|bronze|silver|gold|migr|pipeline|end.to.end|criar|construir|implementar)\b",
    re.IGNORECASE,
)


class Supervisor:
    def __init__(self):
        self._agents = load_all()
        self._supervisor_agent: BaseAgent = self._agents["supervisor"]

    def route(self, user_input: str) -> AgentResult:
        """Roteia o input para o agente correto, possivelmente gerando PRD."""
        parts = user_input.strip().split(maxsplit=1)
        command = parts[0].lower() if parts[0].startswith("/") else "/plan"
        task = parts[1] if len(parts) > 1 else user_input

        if command == "/plan" or _COMPLEX_KEYWORDS.search(task):
            return self._plan_and_delegate(task)

        agent_name = AGENT_COMMANDS.get(command, "supervisor")
        agent = self._agents.get(agent_name, self._supervisor_agent)
        return agent.run(task)

    def _plan_and_delegate(self, task: str) -> AgentResult:
        prd_prompt = (
            f"Crie um PRD conciso para a tarefa abaixo. Inclua:\n"
            f"- Objetivo\n- Entradas esperadas\n- Saídas esperadas\n"
            f"- Agente responsável (um de: spark_expert, sql_expert, pipeline_architect, data_quality, geral)\n"
            f"- Riscos\n\nTarefa: {task}"
        )
        prd_result = self._supervisor_agent.run(prd_prompt)
        prd_content = prd_result.content

        prd_file = OUTPUT_DIR / f"prd_{hash(task) % 100000:05d}.md"
        prd_file.write_text(prd_content)

        agent_match = re.search(
            r"\b(spark_expert|sql_expert|pipeline_architect|data_quality|geral)\b",
            prd_content,
            re.IGNORECASE,
        )
        agent_name = agent_match.group(1).lower() if agent_match else "supervisor"
        agent = self._agents.get(agent_name, self._supervisor_agent)

        execution_result = agent.run(task, context=prd_content)
        return AgentResult(
            content=f"**PRD gerado:** `{prd_file.name}`\n\n---\n\n{execution_result.content}",
            tool_calls_count=prd_result.tool_calls_count + execution_result.tool_calls_count,
            tokens_used=prd_result.tokens_used + execution_result.tokens_used,
        )

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())
