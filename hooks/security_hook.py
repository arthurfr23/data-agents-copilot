"""Hook de segurança — bloqueia padrões destrutivos antes da execução."""

import re

_BLOCKED_PATTERNS = [
    r"\bDROP\s+(TABLE|DATABASE|SCHEMA|CATALOG)\b",
    r"\bTRUNCATE\s+TABLE\b",
    r"\brm\s+-rf\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+push\s+--force\b",
    r"\.env\b",
    r"\.ssh/",
    r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)",  # DELETE sem WHERE
    r"\bSELECT\s+\*\s+FROM\b(?!.*\b(WHERE|LIMIT)\b)",  # SELECT * sem WHERE/LIMIT
]

_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _BLOCKED_PATTERNS]


def check(content: str) -> tuple[bool, str]:
    """Retorna (permitido, motivo). Se bloqueado, permitido=False."""
    for pattern in _COMPILED:
        if pattern.search(content):
            return False, f"Padrão bloqueado detectado: `{pattern.pattern}`"
    return True, ""
