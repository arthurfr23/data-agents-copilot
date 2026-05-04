"""Registry de tools MCP para o loop agentico OpenAI."""

from __future__ import annotations

import json
import logging

from agents.tools.common import COMMON_TOOLS, dispatch_common
from agents.tools.databricks import DATABRICKS_TOOLS, dispatch_databricks
from agents.tools.fabric import FABRIC_TOOLS, dispatch_fabric
from agents.tools.filesystem import FILESYSTEM_TOOLS, dispatch_filesystem
from agents.tools.git import GIT_TOOLS, dispatch_git

logger = logging.getLogger(__name__)

_MCP_REGISTRY: dict[str, tuple[list[dict], callable]] = {
    "common": (COMMON_TOOLS, dispatch_common),
    "databricks": (DATABRICKS_TOOLS, dispatch_databricks),
    "fabric": (FABRIC_TOOLS, dispatch_fabric),
    "filesystem": (FILESYSTEM_TOOLS, dispatch_filesystem),
    "git": (GIT_TOOLS, dispatch_git),
}


def load_tools_for_mcps(mcps: list[str]) -> list[dict]:
    from config.settings import settings

    tools: list[dict] = []
    for mcp in mcps:
        if mcp not in _MCP_REGISTRY:
            logger.warning("MCP '%s' não registrado em agents/tools", mcp)
            continue
        # Só carrega ferramentas da plataforma se ela estiver configurada
        if mcp == "databricks" and not settings.has_databricks():
            logger.debug("MCP 'databricks' ignorado — DATABRICKS_HOST/TOKEN não configurados")
            continue
        if mcp == "fabric" and not settings.has_fabric():
            logger.debug("MCP 'fabric' ignorado — credenciais Azure/Fabric não configuradas")
            continue
        if mcp == "filesystem" and not settings.local_repo_path.strip():
            logger.debug("MCP 'filesystem' ignorado — LOCAL_REPO_PATH não configurado")
            continue
        tools.extend(_MCP_REGISTRY[mcp][0])
    return tools


def dispatch_tool(name: str, arguments: str | dict) -> str:
    args = json.loads(arguments) if isinstance(arguments, str) else arguments
    for _mcp, (tool_defs, dispatch_fn) in _MCP_REGISTRY.items():
        tool_names = {t["function"]["name"] for t in tool_defs}
        if name in tool_names:
            return dispatch_fn(name, args)
    return f"Tool '{name}' não encontrada em nenhum MCP registrado."
