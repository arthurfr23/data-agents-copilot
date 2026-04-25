"""Carrega definições de agentes a partir dos arquivos .md do registry."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from agents.base import AgentConfig, BaseAgent

REGISTRY_DIR = Path(__file__).parent / "registry"

# Prefixos de system prompt por tier
_TIER_PREFIXES = {
    "T1": "Você é um especialista Tier 1 — máxima qualidade, raciocínio detalhado.",
    "T2": "Você é um especialista Tier 2 — domínio específico, respostas focadas.",
    "T3": "Você é um agente Tier 3 — respostas conceituais rápidas e diretas.",
}

AGENT_COMMANDS: dict[str, str] = {
    "/plan": "supervisor",
    "/spark": "spark_expert",
    "/sql": "sql_expert",
    "/pipeline": "pipeline_architect",
    "/quality": "data_quality",
    "/geral": "geral",
    "/review": "supervisor",
}


def _parse_registry_file(path: Path) -> AgentConfig:
    raw = path.read_text()
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)", raw, re.DOTALL)
    if not fm_match:
        raise ValueError(f"Frontmatter inválido em {path}")

    meta = yaml.safe_load(fm_match.group(1))
    body = fm_match.group(2).strip()

    tier = meta.get("tier", "T2")
    prefix = _TIER_PREFIXES.get(tier, "")
    system_prompt = f"{prefix}\n\n{body}" if prefix else body

    return AgentConfig(
        name=meta["name"],
        tier=tier,
        system_prompt=system_prompt,
        skills=meta.get("skills", []),
        tools=[],
    )


def load_all() -> dict[str, BaseAgent]:
    agents: dict[str, BaseAgent] = {}
    for md_file in sorted(REGISTRY_DIR.glob("*.md")):
        config = _parse_registry_file(md_file)
        agents[config.name] = BaseAgent(config)
    return agents


def get_agent_for_command(command: str, agents: dict[str, BaseAgent]) -> BaseAgent | None:
    agent_name = AGENT_COMMANDS.get(command.split()[0])
    return agents.get(agent_name) if agent_name else None
