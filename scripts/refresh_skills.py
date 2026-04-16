"""
Skill Refresh — Atualiza Skills operacionais com documentação recente.

Usa o agente `skill-updater` para refrescar SKILL.md de domínios configurados,
buscando docs atualizadas via context7, tavily e firecrawl.

Uso:
  python scripts/refresh_skills.py                    # refresh dos domínios configurados
  python scripts/refresh_skills.py --domains databricks fabric
  python scripts/refresh_skills.py --domains databricks --force
  python scripts/refresh_skills.py --dry-run          # lista skills sem atualizar

Configuração via .env:
  SKILL_REFRESH_ENABLED=true
  SKILL_REFRESH_INTERVAL_DAYS=3      # pula skills atualizadas há menos de N dias
  SKILL_REFRESH_DOMAINS=databricks,fabric

O script respeita o intervalo configurado — skills atualizadas recentemente são
puladas automaticamente (a menos que --force seja passado).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Garante que a raiz do projeto está no path (para imports locais)
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import settings  # noqa: E402
from config.logging_config import setup_logging  # noqa: E402

logger = logging.getLogger("data_agents.refresh_skills")

# Diretório base das Skills
_SKILLS_DIR = _PROJECT_ROOT / "skills"


def _get_skill_paths(domains: list[str]) -> list[Path]:
    """Retorna todos os SKILL.md dos domínios especificados."""
    paths: list[Path] = []
    for domain in domains:
        domain_dir = _SKILLS_DIR / domain
        if not domain_dir.exists():
            logger.warning(f"Domínio não encontrado: {domain_dir}")
            continue
        skill_files = sorted(
            p
            for p in domain_dir.rglob("SKILL.md")
            if not any(part.startswith("_") or part.upper() == "TEMPLATE" for part in p.parts)
        )
        paths.extend(skill_files)
    return paths


def _get_skill_age_days(skill_path: Path) -> float | None:
    """
    Retorna quantos dias atrás a skill foi atualizada.

    Lê o campo `updated_at` do frontmatter se existir.
    Fallback: data de modificação do arquivo.
    Retorna None se não conseguir determinar a idade.
    """
    try:
        content = skill_path.read_text(encoding="utf-8")

        # Tenta ler updated_at do frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                frontmatter = content[3:end]
                for line in frontmatter.splitlines():
                    if line.strip().startswith("updated_at:"):
                        date_str = line.split(":", 1)[1].strip()
                        try:
                            updated = datetime.strptime(date_str, "%Y-%m-%d").replace(
                                tzinfo=timezone.utc
                            )
                            return (datetime.now(timezone.utc) - updated).days
                        except ValueError:
                            break

        # Fallback: mtime do arquivo
        import os

        mtime = datetime.fromtimestamp(os.path.getmtime(skill_path), tz=timezone.utc)
        return (datetime.now(timezone.utc) - mtime).days

    except Exception:
        return None


def _should_refresh(skill_path: Path, interval_days: int, force: bool) -> tuple[bool, str]:
    """
    Decide se uma skill precisa ser atualizada.

    Retorna (should_refresh, reason).
    """
    if force:
        return True, "force=True"

    age = _get_skill_age_days(skill_path)
    if age is None:
        return True, "não foi possível determinar a idade"

    if age >= interval_days:
        return True, f"{age} dias desde o último refresh (intervalo: {interval_days} dias)"

    return False, f"atualizada há {age} dias (intervalo: {interval_days} dias)"


async def _refresh_skill(skill_path: Path) -> dict:
    """
    Invoca o skill-updater agent para refrescar uma SKILL.md.

    Retorna métricas: {"skill": str, "status": str, "cost": float}.
    """
    from claude_agent_sdk import query, ResultMessage, AssistantMessage, TextBlock
    from agents.supervisor import build_supervisor_options

    rel_path = skill_path.relative_to(_PROJECT_ROOT)
    prompt = (
        f"Atualize a Skill em `{rel_path}` com documentação recente.\n\n"
        f"Caminho absoluto: `{skill_path}`\n\n"
        f"Siga o Protocolo de Refresh completo:\n"
        f"1. Leia o arquivo atual\n"
        f"2. Identifique a biblioteca/ferramenta\n"
        f"3. Busque documentação atualizada via context7, tavily ou firecrawl\n"
        f"4. Atualize o conteúdo e o frontmatter (updated_at: {datetime.now().strftime('%Y-%m-%d')})\n"
        f"5. Salve o arquivo atualizado\n"
        f"6. Gere o relatório final"
    )

    options = build_supervisor_options(platforms=["context7", "tavily", "firecrawl"])
    # Usa apenas o skill-updater, sem o supervisor completo
    options.agents = {
        name: agent for name, agent in (options.agents or {}).items() if name == "skill-updater"
    }
    options.max_turns = 15  # suficiente para uma skill
    options.max_budget_usd = 0.50  # cap por skill

    cost = 0.0
    status = "unknown"
    response_text = ""

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    response_text += block.text
        elif isinstance(message, ResultMessage):
            cost = float(message.total_cost_usd or 0)
            status = "ok"

    if not response_text:
        status = "empty_response"

    return {
        "skill": str(rel_path),
        "status": status,
        "cost": cost,
        "response_preview": response_text[:200] if response_text else "",
    }


async def run_refresh(
    domains: list[str],
    interval_days: int,
    force: bool = False,
    dry_run: bool = False,
    max_concurrent: int = 2,
) -> dict:
    """
    Executa o refresh de todas as skills dos domínios especificados.

    Args:
        domains: Lista de domínios a atualizar (ex: ["databricks", "fabric"])
        interval_days: Pula skills atualizadas há menos de N dias
        force: Se True, atualiza todas independentemente do intervalo
        dry_run: Se True, apenas lista o que seria atualizado sem modificar nada
        max_concurrent: Número máximo de skills atualizadas em paralelo

    Returns:
        Dict com métricas do refresh: {"total", "refreshed", "skipped", "errors", "cost"}
    """
    skill_paths = _get_skill_paths(domains)

    if not skill_paths:
        logger.warning(f"Nenhuma SKILL.md encontrada para os domínios: {domains}")
        return {"total": 0, "refreshed": 0, "skipped": 0, "errors": 0, "cost": 0.0}

    metrics = {
        "total": len(skill_paths),
        "refreshed": 0,
        "skipped": 0,
        "errors": 0,
        "cost": 0.0,
        "details": [],
    }

    print(f"\n{'=' * 60}")
    print(f"Skill Refresh — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Domínios: {', '.join(domains)} | Intervalo: {interval_days}d | Force: {force}")
    print(f"Skills encontradas: {len(skill_paths)}")
    print(f"{'=' * 60}\n")

    # Filtra skills que precisam de atualização
    to_refresh: list[Path] = []
    for skill_path in skill_paths:
        should, reason = _should_refresh(skill_path, interval_days, force)
        rel = skill_path.relative_to(_PROJECT_ROOT)
        if should:
            print(f"  ⏳ {rel} — {reason}")
            to_refresh.append(skill_path)
        else:
            print(f"  ✓  {rel} — pulada ({reason})")
            metrics["skipped"] += 1

    if not to_refresh:
        print("\nNenhuma skill precisa de atualização.")
        return metrics

    if dry_run:
        print(f"\n[dry-run] {len(to_refresh)} skills seriam atualizadas.")
        metrics["refreshed"] = len(to_refresh)
        return metrics

    print(f"\nAtualizando {len(to_refresh)} skills (max {max_concurrent} simultâneas)...\n")

    # Processa em lotes para não sobrecarregar a API
    for i in range(0, len(to_refresh), max_concurrent):
        batch = to_refresh[i : i + max_concurrent]
        tasks = [_refresh_skill(path) for path in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for skill_path, result in zip(batch, results):
            rel = skill_path.relative_to(_PROJECT_ROOT)
            if isinstance(result, Exception):
                print(f"  ✗ {rel} — ERRO: {result}")
                metrics["errors"] += 1
                metrics["details"].append(
                    {"skill": str(rel), "status": "error", "error": str(result)}
                )
            else:
                status = result.get("status", "unknown")
                cost = result.get("cost", 0.0)
                if status == "ok":
                    print(f"  ✅ {rel} — atualizada (${cost:.4f})")
                    metrics["refreshed"] += 1
                else:
                    print(f"  ⚠️  {rel} — {status} (${cost:.4f})")
                    metrics["errors"] += 1
                metrics["cost"] += cost
                metrics["details"].append(result)

    print(f"\n{'=' * 60}")
    print(
        f"Resultado: {metrics['refreshed']} atualizadas | "
        f"{metrics['skipped']} puladas | "
        f"{metrics['errors']} erros | "
        f"Custo: ${metrics['cost']:.4f}"
    )
    print(f"{'=' * 60}\n")

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Atualiza Skills operacionais com documentação recente das plataformas."
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        default=None,
        help="Domínios a atualizar (ex: databricks fabric). "
        f"Padrão: {settings.skill_refresh_domains}",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help=f"Intervalo mínimo em dias entre refreshes. "
        f"Padrão: {settings.skill_refresh_interval_days}",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Atualiza todas as skills independentemente do intervalo.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lista as skills que seriam atualizadas sem modificar nada.",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=2,
        help="Número máximo de skills atualizadas em paralelo. Padrão: 2.",
    )

    args = parser.parse_args()

    # Resolve configurações (CLI > settings > padrão)
    domains = args.domains or [
        d.strip() for d in settings.skill_refresh_domains.split(",") if d.strip()
    ]
    interval = args.interval or settings.skill_refresh_interval_days

    if not settings.skill_refresh_enabled and not args.force:
        print("Skill refresh desabilitado (SKILL_REFRESH_ENABLED=false). Use --force para forçar.")
        sys.exit(0)

    setup_logging(log_level="WARNING", enable_console=False)

    asyncio.run(
        run_refresh(
            domains=domains,
            interval_days=interval,
            force=args.force,
            dry_run=args.dry_run,
            max_concurrent=args.concurrent,
        )
    )


if __name__ == "__main__":
    main()
