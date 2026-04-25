"""Hook de auditoria — registra todas as interações em JSONL."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
AUDIT_FILE = LOG_DIR / "audit.jsonl"

logger = logging.getLogger(__name__)


def record(agent: str, task: str, tokens_used: int, tool_calls: int) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "task_preview": task[:200],
        "tokens_used": tokens_used,
        "tool_calls": tool_calls,
    }
    with AUDIT_FILE.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.debug("Audit: %s", entry)
