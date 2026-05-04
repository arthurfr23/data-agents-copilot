"""hooks.output_compressor — Trunca respostas verbosas.

Garante que respostas longas de MCP ou agentes não desperdicem
janela de contexto em chamadas subsequentes.

    compress("texto longo...", max_chars=8000)
    → head + [...N chars truncados...] + tail
"""
from __future__ import annotations

def compress(text: str, max_chars: int = 8000) -> str:
    """
    Trunca `text` para no máximo `max_chars` caracteres.
    Preserva os primeiros 2/3 e os últimos 1/3 do limite.
    Se o texto já couber em `max_chars`, retorna inalterado.
    """
    if max_chars <= 0 or len(text) <= max_chars:
        return text

    head_limit = max_chars * 2 // 3
    tail_limit = max_chars - head_limit
    removed = len(text) - head_limit - tail_limit
    marker = f"\n\n[...{removed} caracteres truncados...]\n\n"
    return text[:head_limit] + marker + text[-tail_limit:]
