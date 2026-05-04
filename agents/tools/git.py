"""Tools git para atuar em repositório local (LOCAL_REPO_PATH).

Operações permitidas: status, log, diff, ls-files, add, commit.
Operações bloqueadas: push, reset --hard, checkout, branch -D, force.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_BLOCKED = frozenset(["push", "reset", "checkout", "branch", "rebase", "clean"])
_TIMEOUT = 30


def _repo_root() -> Path:
    from config.settings import settings
    root = settings.local_repo_path.strip()
    if not root:
        raise RuntimeError(
            "LOCAL_REPO_PATH não configurado. Defina no .env antes de usar git tools."
        )
    return Path(root).resolve()


def _run(args: list[str]) -> str:
    root = _repo_root()
    result = subprocess.run(
        ["git"] + args,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )
    out = result.stdout.strip()
    err = result.stderr.strip()
    if result.returncode != 0:
        return f"[exit {result.returncode}]\n{err or out}"
    return out or "(sem output)"


# ── tools ────────────────────────────────────────────────────────────────────

def _git_status() -> str:
    return _run(["status", "--short", "--branch"])


def _git_log(n: int = 10) -> str:
    n = min(max(int(n), 1), 50)
    return _run(["log", f"-{n}", "--oneline", "--decorate"])


def _git_diff(ref: str = "HEAD") -> str:
    return _run(["diff", ref])


def _git_ls_files(path: str = ".") -> str:
    return _run(["ls-files", path])


def _git_add(paths: list[str]) -> str:
    if not paths:
        return "Nenhum path fornecido para git add."
    return _run(["add", "--"] + paths)


def _git_commit(message: str) -> str:
    if not message.strip():
        return "Mensagem de commit não pode ser vazia."
    return _run(["commit", "-m", message])


# ── schema OpenAI + dispatcher ───────────────────────────────────────────────

GIT_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Retorna o status do repositório local (branch atual, arquivos modificados/staged/untracked).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Retorna os últimos N commits do repositório local (max 50).",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "description": "Número de commits a retornar (default: 10).",
                        "default": 10,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Retorna o diff do repositório local em relação a uma referência (default: HEAD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "string",
                        "description": "Referência git (branch, commit hash, HEAD~1, etc). Default: 'HEAD'.",
                        "default": "HEAD",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_ls_files",
            "description": "Lista arquivos rastreados pelo git em um caminho do repositório.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Caminho relativo ao LOCAL_REPO_PATH (default: '.' para tudo).",
                        "default": ".",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_add",
            "description": "Faz stage de arquivos para o próximo commit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de caminhos relativos ao LOCAL_REPO_PATH para stage.",
                    }
                },
                "required": ["paths"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Cria um commit com os arquivos atualmente em stage. Nunca usa --no-verify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Mensagem de commit.",
                    }
                },
                "required": ["message"],
            },
        },
    },
]


def dispatch_git(name: str, args: dict) -> str:
    try:
        if name == "git_status":
            return _git_status()
        if name == "git_log":
            return _git_log(args.get("n", 10))
        if name == "git_diff":
            return _git_diff(args.get("ref", "HEAD"))
        if name == "git_ls_files":
            return _git_ls_files(args.get("path", "."))
        if name == "git_add":
            return _git_add(args.get("paths", []))
        if name == "git_commit":
            return _git_commit(args["message"])
        return f"Tool desconhecida: {name}"
    except Exception as exc:
        logger.error("dispatch_git %s: %s", name, exc)
        return f"Erro em {name}: {exc}"
