"""Tools utilitários comuns — disponíveis para qualquer agente com mcps: [common]."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


def _write_output_file(filename: str, content: str) -> str:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = (_OUTPUT_DIR / filename).resolve()
    # Garante que o arquivo fica dentro de output/ (evita path traversal)
    if not str(path).startswith(str(_OUTPUT_DIR.resolve())):
        return json.dumps({"error": "filename inválido — path fora do diretório output/"})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return json.dumps({"saved": str(path), "bytes": len(content.encode())})


COMMON_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "write_output_file",
            "description": (
                "Salva conteúdo em um arquivo dentro do diretório output/ do projeto. "
                "Use para persistir resultados, relatórios ou bases de conhecimento em Markdown. "
                "Exemplo: filename='fabric-catalog.md', content='# Catálogo\\n...'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Nome do arquivo com extensão (ex: 'fabric-catalog.md'). "
                        "Pode incluir subdiretório relativo ao output/ (ex: 'kb/fabric-catalog.md').",
                    },
                    "content": {
                        "type": "string",
                        "description": "Conteúdo completo do arquivo.",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    },
]


def dispatch_common(name: str, args: dict) -> str:
    if name == "write_output_file":
        # Aceita tanto "filename" quanto "path" como nome do parâmetro
        filename = args.get("filename") or args.get("path", "")
        content = args.get("content", "")
        if not filename:
            return json.dumps({"error": "filename obrigatório"})
        if not content:
            return json.dumps({"error": "content obrigatório — forneça o conteúdo completo do arquivo"})
        return _write_output_file(filename, content)
    return f"Tool common '{name}' não reconhecida."
