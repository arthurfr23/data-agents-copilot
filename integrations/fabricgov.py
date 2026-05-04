"""Wrapper para o fabricgov — assessment de governança do Microsoft Fabric.

Usa a Python API do fabricgov diretamente (sem subprocess CLI), o que permite
passar tenant_id explícito no device flow e SP.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_PACKAGE = "fabricgov"
_GIT_URL = "git+https://github.com/luhborba/fabricgov.git"
_BIN_DIR = Path(sys.executable).parent
_DEFAULT_OUTPUT_DIR = "output/fabricgov"


# ── instalação ───────────────────────────────────────────────────────────────

def is_installed() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", _PACKAGE],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def install() -> bool:
    logger.info("fabricgov não encontrado — instalando via git...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--ignore-requires-python", _GIT_URL],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("Falha ao instalar fabricgov: %s", result.stderr)
    return result.returncode == 0


# ── auth ─────────────────────────────────────────────────────────────────────

def _get_settings():
    from config.settings import settings
    return settings


def detect_auth_mode() -> str:
    """Retorna o modo de auth para o fabricgov.

    FABRIC_AUTH_MODE=interactive/device → device flow.
    FABRICGOV_AUTH_MODE=sp             → SP explícito.
    Fallback: sp se credenciais disponíveis, senão device.
    """
    env = os.environ

    # Override explícito para fabricgov
    fabricgov_mode = env.get("FABRICGOV_AUTH_MODE", "").lower()
    if fabricgov_mode in ("sp", "device"):
        return fabricgov_mode

    # FABRIC_AUTH_MODE=interactive/device → device flow (env ou settings)
    fabric_mode = (env.get("FABRIC_AUTH_MODE") or _get_settings().fabric_auth_mode or "").lower()
    if fabric_mode in ("interactive", "device"):
        return "device"

    # Detecta por credenciais disponíveis
    s = _get_settings()
    has_sp = bool(
        (env.get("FABRICGOV_CLIENT_ID") or env.get("AZURE_CLIENT_ID") or s.azure_client_id)
        and (env.get("FABRICGOV_CLIENT_SECRET") or env.get("AZURE_CLIENT_SECRET") or s.azure_client_secret)
        and (env.get("FABRICGOV_TENANT_ID") or env.get("AZURE_TENANT_ID") or s.azure_tenant_id)
    )
    return "sp" if has_sp else "device"


def _build_auth(auth_mode: str):
    """Cria o objeto de autenticação do fabricgov com tenant_id explícito."""
    from fabricgov.auth import ServicePrincipalAuth, DeviceFlowAuth

    s = _get_settings()
    env = os.environ

    if auth_mode == "sp":
        tenant_id = env.get("FABRICGOV_TENANT_ID") or env.get("AZURE_TENANT_ID") or s.azure_tenant_id or ""
        client_id = env.get("FABRICGOV_CLIENT_ID") or env.get("AZURE_CLIENT_ID") or s.azure_client_id or ""
        client_secret = env.get("FABRICGOV_CLIENT_SECRET") or env.get("AZURE_CLIENT_SECRET") or s.azure_client_secret or ""
        return ServicePrincipalAuth.from_params(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

    # device flow — passa tenant_id explícito para evitar token multi-tenant
    tenant_id = env.get("FABRICGOV_TENANT_ID") or env.get("AZURE_TENANT_ID") or s.azure_tenant_id or None
    _clear_stale_token_cache(tenant_id)
    return DeviceFlowAuth(tenant_id=tenant_id)


def _clear_stale_token_cache(tenant_id: str | None) -> None:
    """Remove o cache de token se ele foi obtido sem tenant_id (common)."""
    cache_file = Path.home() / ".fabricgov_token_cache.json"
    if not cache_file.exists() or not tenant_id:
        return
    try:
        import json, jwt  # noqa: F401
        data = json.loads(cache_file.read_text())
        token = data.get("access_token", "")
        # Decodifica sem verificar assinatura para ver o tid do token
        payload = jwt.decode(token, options={"verify_signature": False})
        cached_tid = payload.get("tid", "")
        if cached_tid and cached_tid != tenant_id:
            cache_file.unlink()
            logger.info("Token cache removido (tenant_id diferente: %s)", cached_tid)
    except Exception:
        # jwt não instalado ou token inválido — remove por precaução
        cache_file.unlink(missing_ok=True)


# ── assessment ────────────────────────────────────────────────────────────────

def run_assessment(
    command: str = "all",
    output_dir: str = _DEFAULT_OUTPUT_DIR,
    days: int = 7,
    lang: str = "pt",
    auth_mode: str | None = None,
) -> dict:
    """Executa collect + analyze + report via Python API do fabricgov.

    Args:
        command:    'all' ou nome de um coletor individual ('inventory', 'activity', etc.)
        output_dir: Diretório de saída.
        days:       Dias de histórico de atividade (só para 'all' e 'activity').
        lang:       Idioma do relatório ('pt' ou 'en').
        auth_mode:  'sp' ou 'device' (None = auto-detectar).

    Returns:
        dict com chaves: status, auth_mode, run_dir, findings, report_path, error.
    """
    if not is_installed() and not install():
        return {
            "status": "error",
            "error": f"Não foi possível instalar fabricgov. Rode:\n  pip install {_GIT_URL}",
        }

    _auth_mode = auth_mode or detect_auth_mode()
    result: dict = {"status": "ok", "auth_mode": _auth_mode}

    try:
        from fabricgov import FabricGov

        auth = _build_auth(_auth_mode)
        fg = FabricGov(auth)

        # ── coleta ────────────────────────────────────────────────────────────
        if command == "all":
            run_dir = fg.collect.all(output_dir=output_dir, days=days)
        elif command == "inventory":
            fg.collect.inventory(output_dir=output_dir)
            run_dir = Path(output_dir)
        elif command == "activity":
            fg.collect.activity(output_dir=output_dir, days=days)
            run_dir = Path(output_dir)
        else:
            method = getattr(fg.collect, command.replace("-", "_"), None)
            if method is None:
                return {"status": "error", "error": f"Comando desconhecido: {command}"}
            method(output_dir=output_dir)
            run_dir = Path(output_dir)

        result["run_dir"] = str(run_dir)

        # ── analyze ───────────────────────────────────────────────────────────
        try:
            findings = fg.analyze(source_dir=run_dir, lang=lang)
            result["findings"] = findings
        except FileNotFoundError:
            result["findings"] = []

        # ── report ────────────────────────────────────────────────────────────
        report_path = Path(run_dir) / "report.html"
        try:
            fg.report(output_path=report_path, lang=lang, source_dir=run_dir)
            result["report_path"] = str(report_path)
        except Exception as e:
            logger.warning("Relatório HTML não gerado: %s", e)
            result["report_path"] = None

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


# ── formatação ────────────────────────────────────────────────────────────────

def format_result(result: dict) -> str:
    if result["status"] == "error":
        error = result.get("error", "")
        auth = result.get("auth_mode", "desconhecido")
        msg = f"❌ **fabricgov falhou**\n\nAuth mode: `{auth}`\n\nErro:\n```\n{error}\n```"
        if "device" in auth and "device flow" in error.lower() or "token" in error.lower():
            msg += (
                "\n\n**Para autenticar:** abra um terminal e rode:\n"
                f"```\n{_BIN_DIR}/fabricgov auth device\n```"
            )
        elif "Service Principal" in error or "invalid_client" in error:
            msg += (
                "\n\nVerifique se o Service Principal existe no tenant e tem "
                "`Tenant.Read.All` nas APIs Admin do Fabric."
            )
        return msg

    auth = result.get("auth_mode", "?")
    run_dir = result.get("run_dir", "")
    report_path = result.get("report_path", "")
    findings: list[dict] = result.get("findings", [])

    parts = [
        "## fabricgov Assessment — Microsoft Fabric",
        f"**Auth:** `{auth}` | **Run:** `{run_dir}`",
        "",
    ]

    if findings:
        critical = [f for f in findings if f.get("severity") == "CRITICAL"]
        high = [f for f in findings if f.get("severity") == "HIGH"]
        medium = [f for f in findings if f.get("severity") == "MEDIUM"]

        parts.append("### Findings de Governança")
        for group, label in [(critical, "🔴 CRITICAL"), (high, "🟠 HIGH"), (medium, "🟡 MEDIUM")]:
            for f in group:
                count = f.get("count", "")
                parts.append(f"- **{label}** — {f.get('message', '')} ({count})")
        parts.append("")
    else:
        parts += ["*Nenhum finding gerado — verifique se a coleta completou.*", ""]

    if report_path:
        parts.append(f"**Relatório HTML:** `{report_path}`")

    return "\n".join(parts)
