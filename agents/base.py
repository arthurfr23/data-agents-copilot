"""Base agent class — executa loop agentico via GitHub Copilot API ou Anthropic SDK."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai.types.chat import ChatCompletionMessageParam

from config.settings import settings

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent / "skills" / "skills"


@dataclass
class AgentConfig:
    name: str
    tier: str
    system_prompt: str
    skills: list[str] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)
    kb_domains: list[str] = field(default_factory=list)
    model: str | None = None  # override do tier; quando None, usa settings.tier_model_map[tier]


# Tools cujo sucesso é o próprio entregável — QA verify é desnecessário após execução
_TERMINAL_TOOLS: frozenset[str] = frozenset({
    "write_output_file",
})


@dataclass
class AgentResult:
    content: str
    tool_calls_count: int
    tokens_used: int
    terminal_tool_executed: bool = False


def _is_success(tool_result: str) -> bool:
    """Retorna True se o resultado de uma tool não contém chave 'error'."""
    try:
        return "error" not in json.loads(tool_result)
    except (json.JSONDecodeError, TypeError):
        return bool(tool_result) and "error" not in tool_result.lower()


def _parse_retry_after(exc: Exception) -> int | None:
    """Extrai Retry-After do header da resposta 429, com fallback para None."""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", {}) or {}
    value = headers.get("retry-after") or headers.get("Retry-After")
    try:
        return max(int(float(value)), 5)
    except (TypeError, ValueError):
        return None


def _openai_tools_to_anthropic(tools: list[dict]) -> list[dict]:
    result = []
    for t in tools:
        if t.get("type") == "function":
            fn = t["function"]
            result.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
    return result


class BaseAgent:
    # Cache compartilhado entre todas as instâncias — leitura de disco por skill, não por agente
    _CLASS_SKILL_CACHE: dict[str, str] = {}

    def __init__(self, config: AgentConfig):
        self.config = config
        # Frontmatter `model:` vence `tier_model_map`; tier é o fallback.
        self.model = config.model or settings.model_for_tier(config.tier)
        self.max_turns = settings.turns_for_tier(config.tier)

    def _load_skill(self, skill_name: str) -> str:
        if skill_name in BaseAgent._CLASS_SKILL_CACHE:
            return BaseAgent._CLASS_SKILL_CACHE[skill_name]
        skill_path = SKILLS_DIR / skill_name / "SKILL.md"
        if skill_path.exists():
            content = skill_path.read_text()
            BaseAgent._CLASS_SKILL_CACHE[skill_name] = content
            return content
        logger.warning("Skill '%s' não encontrada em %s", skill_name, SKILLS_DIR)
        return ""

    def _build_system(self) -> str:
        parts = [self.config.system_prompt]
        for skill in self.config.skills:
            content = self._load_skill(skill)
            if content:
                parts.append(f"\n\n---\n## Skill: {skill}\n{content}")
        parts.append(
            "\n\n---\n"
            "## REGRA CRÍTICA — Tool Calls\n"
            "NUNCA gere `<function_calls>`, `<invoke>`, `<parameter>`, `<function_response>` "
            "ou qualquer tag XML como texto de output.\n"
            "Ferramentas DEVEM ser chamadas exclusivamente via o mecanismo tool_use nativo da API.\n"
            "Gerar XML como texto NÃO executa nenhuma ferramenta — é apenas texto inerte."
        )
        return "\n".join(parts)

    def run(self, task: str, context: str = "", json_mode: bool = False) -> AgentResult:
        base_system = self._build_system()
        # Context (KB + memória) vai no system para ser cacheado e sair do histórico crescente
        system = f"{base_system}\n\n---\n## Contexto\n{context}" if context else base_system
        if self.model.startswith("claude") and settings.anthropic_api_key:
            return self._run_anthropic(task, system, json_mode)
        return self._run_openai(task, system, json_mode)

    # ── Anthropic SDK (prompt caching) ───────────────────────────────────────

    def _run_anthropic(self, task: str, system: str, json_mode: bool = False) -> AgentResult:
        import time
        from anthropic import Anthropic, RateLimitError

        client = Anthropic(api_key=settings.anthropic_api_key)
        ant_tools = _openai_tools_to_anthropic(self.config.tools) if self.config.tools else []

        messages: list[dict] = [{"role": "user", "content": task}]

        total_tokens = 0
        total_tool_calls = 0
        terminal_executed = False

        # Limites de chars para o histórico de mensagens.
        # O conteúdo já foi processado — não precisa manter enorme na memória.
        _TOOL_INPUT_MAX_CHARS = 8_000
        _TOOL_RESULT_MAX_CHARS = 24_000

        for _turn in range(self.max_turns):
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": settings.llm_max_tokens,
                "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                "messages": messages,
            }
            if ant_tools:
                kwargs["tools"] = ant_tools

            for attempt in range(4):
                try:
                    with client.messages.stream(**kwargs) as stream:
                        response = stream.get_final_message()
                    break
                except RateLimitError as exc:
                    if attempt == 3:
                        raise
                    retry_after = _parse_retry_after(exc) or (60 * 2 ** attempt)
                    logger.warning(
                        "Rate limit 429 — aguardando %ds (tentativa %d/4). "
                        "Backlog de tokens na janela de 1 min; aguardar é a única solução.",
                        retry_after, attempt + 1,
                    )
                    time.sleep(retry_after)
            usage = response.usage
            total_tokens += (
                usage.input_tokens
                + usage.output_tokens
                + getattr(usage, "cache_read_input_tokens", 0)
                + getattr(usage, "cache_creation_input_tokens", 0)
            )

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if tool_uses:
                total_tool_calls += len(tool_uses)
                for _tu in tool_uses:
                    logger.info("🔧 tool_use: %s", _tu.name)
                    print(f"  🔧 {_tu.name}", flush=True)
                # Converte para dicts e trunca inputs grandes antes de armazenar no histórico.
                # O arquivo já foi salvo — não precisa reenviar conteúdo enorme em turns futuros.
                stored_content = []
                for block in response.content:
                    if block.type == "tool_use":
                        truncated_input = {}
                        for k, v in block.input.items():
                            if isinstance(v, str) and len(v) > _TOOL_INPUT_MAX_CHARS:
                                truncated_input[k] = v[:_TOOL_INPUT_MAX_CHARS] + f"...[{len(v) - _TOOL_INPUT_MAX_CHARS} chars omitidos]"
                            else:
                                truncated_input[k] = v
                        stored_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": truncated_input,
                        })
                    elif block.type == "text":
                        stored_content.append({"type": "text", "text": block.text})
                    else:
                        stored_content.append(block)
                messages.append({"role": "assistant", "content": stored_content})
                tool_results = []
                for tu in tool_uses:
                    result = self._dispatch_tool(tu.name, tu.input)
                    if tu.name in _TERMINAL_TOOLS and _is_success(result):
                        terminal_executed = True
                    result_str = str(result)
                    if len(result_str) > _TOOL_RESULT_MAX_CHARS:
                        result_str = (
                            result_str[:_TOOL_RESULT_MAX_CHARS]
                            + f"\n...[{len(result_str) - _TOOL_RESULT_MAX_CHARS} chars omitidos no histórico]"
                        )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": result_str,
                    })
                messages.append({"role": "user", "content": tool_results})
            else:
                return AgentResult(
                    content=text_blocks[0].text if text_blocks else "",
                    tool_calls_count=total_tool_calls,
                    tokens_used=total_tokens,
                    terminal_tool_executed=terminal_executed,
                )

        return AgentResult(
            content="Max turns reached.",
            tool_calls_count=total_tool_calls,
            tokens_used=total_tokens,
            terminal_tool_executed=terminal_executed,
        )

    # ── OpenAI SDK (Copilot ou OpenAI-compat) ────────────────────────────────

    def _run_openai(self, task: str, system: str, json_mode: bool) -> AgentResult:
        # System já contém o context — sai do histórico crescente
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]

        total_tokens = 0
        total_tool_calls = 0
        terminal_executed = False

        for _turn in range(self.max_turns):
            kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
            if self.config.tools:
                kwargs["tools"] = self.config.tools
                kwargs["tool_choice"] = "auto"
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = settings.llm_client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            total_tokens += response.usage.total_tokens if response.usage else 0

            if msg.tool_calls:
                total_tool_calls += len(msg.tool_calls)
                messages.append(msg)
                for tc in msg.tool_calls:
                    result = self._dispatch_tool(tc.function.name, tc.function.arguments)
                    if tc.function.name in _TERMINAL_TOOLS and _is_success(result):
                        terminal_executed = True
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result),
                    })
            else:
                return AgentResult(
                    content=msg.content or "",
                    tool_calls_count=total_tool_calls,
                    tokens_used=total_tokens,
                    terminal_tool_executed=terminal_executed,
                )

        return AgentResult(
            content=messages[-1].get("content", "Max turns reached."),
            tool_calls_count=total_tool_calls,
            tokens_used=total_tokens,
            terminal_tool_executed=terminal_executed,
        )

    def _dispatch_tool(self, name: str, arguments: str | dict) -> str:
        """Roteia tool calls para agents/tools (databricks, fabric)."""
        from agents.tools import dispatch_tool
        args_parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
        logger.debug("Tool call: %s(%s)", name, args_parsed)
        return dispatch_tool(name, args_parsed)
