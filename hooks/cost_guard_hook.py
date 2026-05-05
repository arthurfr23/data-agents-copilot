"""Hook de controle de custo — classificação por operação e alerta de tokens.

Estado por sessão (não global) — multi-user no Chainlit não contamina contadores
entre usuários. Callers passam session_id; REPL usa "default".
"""

import logging

from config.settings import settings

logger = logging.getLogger(__name__)

_HIGH_COST_PATTERNS = [
    "execute_job", "start_cluster", "start_pipeline",
    "create_pipeline", "create_job",
]
_MEDIUM_COST_PATTERNS = ["execute_sql", "run_query", "submit_run"]

_SESSION_STATE: dict[str, dict] = {}


def _state(session_id: str) -> dict:
    return _SESSION_STATE.setdefault(session_id, {"total_tokens": 0, "high_count": 0})


def classify_operation(tool_name: str) -> str:
    tl = tool_name.lower()
    if any(p in tl for p in _HIGH_COST_PATTERNS):
        return "HIGH"
    if any(p in tl for p in _MEDIUM_COST_PATTERNS):
        return "MEDIUM"
    return "LOW"


def track(tool_name: str, tokens_used: int, session_id: str = "default") -> None:
    s = _state(session_id)
    level = classify_operation(tool_name)
    s["total_tokens"] += tokens_used

    if level == "HIGH":
        s["high_count"] += 1
        if s["high_count"] > 5:
            logger.warning(
                "ALERTA[%s]: %d operações HIGH nesta sessão. Verifique o custo.",
                session_id, s["high_count"],
            )

    budget = settings.max_budget_tokens
    pct = s["total_tokens"] / budget if budget else 0
    if pct >= 0.95:
        logger.error(
            "CRÍTICO[%s]: 95%% do budget de tokens atingido (%d/%d).",
            session_id, s["total_tokens"], budget,
        )
    elif pct >= 0.80:
        logger.warning(
            "AVISO[%s]: 80%% do budget de tokens atingido (%d/%d).",
            session_id, s["total_tokens"], budget,
        )


def session_summary(session_id: str = "default") -> dict:
    s = _state(session_id)
    return {
        "total_tokens": s["total_tokens"],
        "high_ops": s["high_count"],
        "budget": settings.max_budget_tokens,
        "budget_pct": round(s["total_tokens"] / settings.max_budget_tokens * 100, 1)
        if settings.max_budget_tokens
        else 0,
    }


def reset(session_id: str = "default") -> None:
    """Reseta contadores da sessão. Útil em testes e ao iniciar nova sessão."""
    _SESSION_STATE.pop(session_id, None)
