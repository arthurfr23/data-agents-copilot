"""Tools de filesystem para atuar em repositório local (LOCAL_REPO_PATH)."""

from __future__ import annotations

import glob
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_READ_BYTES = 100_000


def _repo_root() -> Path:
    from config.settings import settings
    root = settings.local_repo_path.strip()
    if not root:
        raise RuntimeError(
            "LOCAL_REPO_PATH não configurado. Defina no .env antes de usar filesystem tools."
        )
    return Path(root).resolve()


def _safe_path(relative: str) -> Path:
    root = _repo_root()
    target = (root / relative).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError(f"Path traversal bloqueado: {relative!r}")
    return target


# ── tools ────────────────────────────────────────────────────────────────────

def _repo_read_file(path: str) -> str:
    target = _safe_path(path)
    if not target.exists():
        return f"Arquivo não encontrado: {path}"
    if not target.is_file():
        return f"Não é um arquivo: {path}"
    raw = target.read_bytes()
    if len(raw) > _MAX_READ_BYTES:
        return target.read_text(errors="replace")[:_MAX_READ_BYTES] + "\n...[truncado]"
    return target.read_text(errors="replace")


def _repo_write_file(path: str, content: str) -> str:
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Arquivo escrito: {path} ({len(content)} bytes)"


def _repo_list_files(path: str = ".", pattern: str = "**/*", recursive: bool = True) -> str:
    root = _repo_root()
    base = _safe_path(path)
    if not base.exists():
        return f"Caminho não encontrado: {path}"
    full_pattern = str(base / pattern)
    matches = glob.glob(full_pattern, recursive=recursive)
    files = sorted(
        str(Path(m).relative_to(root))
        for m in matches
        if Path(m).is_file()
    )
    if not files:
        return "Nenhum arquivo encontrado."
    return "\n".join(files[:500])


# ── schema OpenAI + dispatcher ───────────────────────────────────────────────

FILESYSTEM_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "repo_read_file",
            "description": "Lê o conteúdo de um arquivo no repositório local (até 100KB).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Caminho relativo ao LOCAL_REPO_PATH (ex: 'src/bronze/nb_brz_contas.py')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "repo_write_file",
            "description": "Escreve (ou sobrescreve) um arquivo no repositório local. Cria diretórios intermediários automaticamente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Caminho relativo ao LOCAL_REPO_PATH.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Conteúdo a escrever no arquivo.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "repo_list_files",
            "description": "Lista arquivos no repositório local com suporte a glob.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Diretório base relativo ao LOCAL_REPO_PATH (default: '.').",
                        "default": ".",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Padrão glob (default: '**/*' para tudo recursivo).",
                        "default": "**/*",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Se True, busca recursivamente (default: true).",
                        "default": True,
                    },
                },
                "required": [],
            },
        },
    },
]


def dispatch_filesystem(name: str, args: dict) -> str:
    try:
        if name == "repo_read_file":
            return _repo_read_file(args["path"])
        if name == "repo_write_file":
            return _repo_write_file(args["path"], args["content"])
        if name == "repo_list_files":
            return _repo_list_files(
                args.get("path", "."),
                args.get("pattern", "**/*"),
                args.get("recursive", True),
            )
        return f"Tool desconhecida: {name}"
    except Exception as exc:
        logger.error("dispatch_filesystem %s: %s", name, exc)
        return f"Erro em {name}: {exc}"
