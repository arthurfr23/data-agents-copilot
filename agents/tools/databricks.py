"""Tools Databricks para o loop agentico — via databricks-sdk."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from databricks.sdk.errors import DatabricksError
from databricks.sdk.service.sql import Disposition, Format, StatementState

from config.settings import settings

logger = logging.getLogger(__name__)

_MAX_LIST_RESULTS = 200


# ---------------------------------------------------------------------------
# Client accessor
# ---------------------------------------------------------------------------

def _client():
    return settings.databricks_client


def _truncated_list(items: list, label: str) -> list:
    if len(items) > _MAX_LIST_RESULTS:
        logger.info("%s truncado: %d → %d", label, len(items), _MAX_LIST_RESULTS)
    return items[:_MAX_LIST_RESULTS]


# ---------------------------------------------------------------------------
# Implementações
# ---------------------------------------------------------------------------

def _dbr_sql_execute(statement: str, catalog: str = "", schema: str = "") -> str:
    wh_id = settings.databricks_sql_warehouse_id
    if not wh_id:
        return "DATABRICKS_SQL_WAREHOUSE_ID não configurado."
    catalog = catalog or settings.databricks_catalog
    schema = schema or settings.databricks_schema

    resp = _client().statement_execution.execute_statement(
        warehouse_id=wh_id,
        statement=statement,
        catalog=catalog,
        schema=schema,
        wait_timeout="50s",
        disposition=Disposition.INLINE,
        format=Format.JSON_ARRAY,
    )

    state = resp.status.state if resp.status else None
    if state == StatementState.SUCCEEDED:
        cols = [c.name for c in resp.manifest.schema.columns] if resp.manifest else []
        rows = resp.result.data_array if resp.result else []
        if not rows:
            return f"Query OK, 0 linhas. Colunas: {cols}"
        preview = rows[:50]
        result = {"columns": cols, "rows": preview, "total_rows": len(rows)}
        if len(rows) > 50:
            result["truncated"] = True
            result["message"] = f"Mostrando 50 de {len(rows)} linhas."
        return json.dumps(result, ensure_ascii=False)

    # Query não finalizou — retorna statement_id para polling
    stmt_id = resp.statement_id if resp.statement_id else None
    state_val = state.value if state else "UNKNOWN"
    error = resp.status.error if resp.status else None
    detail = error.message if error else ""
    result = {"status": state_val, "detail": detail}
    if stmt_id:
        result["statement_id"] = stmt_id
        result["message"] = "Use dbr_get_statement_status para acompanhar."
    return json.dumps(result)


def _dbr_get_statement_status(statement_id: str) -> str:
    resp = _client().statement_execution.get_statement(statement_id=statement_id)
    state = resp.status.state if resp.status else None
    if state == StatementState.SUCCEEDED:
        cols = [c.name for c in resp.manifest.schema.columns] if resp.manifest else []
        rows = resp.result.data_array if resp.result else []
        preview = rows[:50]
        result = {"columns": cols, "rows": preview, "total_rows": len(rows)}
        if len(rows) > 50:
            result["truncated"] = True
        return json.dumps(result, ensure_ascii=False)
    state_val = state.value if state else "UNKNOWN"
    error = resp.status.error if resp.status else None
    return json.dumps({"status": state_val, "detail": error.message if error else ""})


def _dbr_cancel_statement(statement_id: str) -> str:
    _client().statement_execution.cancel_execution(statement_id=statement_id)
    return json.dumps({"status": "cancelled", "statement_id": statement_id})


def _dbr_list_catalogs() -> str:
    all_catalogs = [c.name for c in _client().catalogs.list() if c.name]
    catalogs = _truncated_list(all_catalogs, "catalogs")
    return json.dumps(catalogs)


def _dbr_list_schemas(catalog: str = "") -> str:
    catalog = catalog or settings.databricks_catalog
    all_schemas = [s.name for s in _client().schemas.list(catalog_name=catalog) if s.name]
    schemas = _truncated_list(all_schemas, "schemas")
    return json.dumps(schemas)


def _dbr_list_tables(catalog: str = "", schema: str = "") -> str:
    catalog = catalog or settings.databricks_catalog
    schema = schema or settings.databricks_schema
    all_tables = [
        {"name": t.name, "type": t.table_type.value if t.table_type else "", "full": t.full_name or ""}
        for t in _client().tables.list(catalog_name=catalog, schema_name=schema)
    ]
    tables = _truncated_list(all_tables, "tables")
    return json.dumps(tables)


def _dbr_get_table_schema(full_name: str) -> str:
    table = _client().tables.get(full_name=full_name)
    cols = [
        {"name": c.name, "type": c.type_text or "", "nullable": c.nullable if c.nullable is not None else True}
        for c in (table.columns or [])
    ]
    props = {k: v for k, v in (table.properties or {}).items()}
    return json.dumps({"table": full_name, "columns": cols, "properties": props})


def _dbr_run_job(
    job_id: str,
    notebook_params: dict | None = None,
    wait_for_completion: bool = False,
    timeout_seconds: int = 600,
) -> str:
    kwargs: dict = {"job_id": int(job_id)}
    if notebook_params:
        kwargs["notebook_params"] = notebook_params
    run = _client().jobs.run_now(**kwargs)
    run_id = run.run_id

    if not wait_for_completion:
        # number_in_job foi descontinuado em versões recentes do SDK
        try:
            number_in_job = run.number_in_job
        except (AttributeError, KeyError):
            number_in_job = None
        return json.dumps({"run_id": run_id, "number_in_job": number_in_job})

    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        status = _client().jobs.get_run(run_id=run_id)
        lcs = status.state.life_cycle_state.value if status.state and status.state.life_cycle_state else "UNKNOWN"
        if lcs in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            rs = status.state.result_state.value if status.state and status.state.result_state else None
            return json.dumps({
                "run_id": run_id,
                "life_cycle_state": lcs,
                "result_state": rs,
                "state_message": status.state.state_message if status.state else None,
                "start_time": status.start_time,
                "end_time": status.end_time,
            })
        time.sleep(15)

    elapsed = int(time.monotonic() - start)
    return json.dumps({
        "run_id": run_id,
        "status": "timeout",
        "message": f"Job não finalizou em {elapsed}s. Use dbr_get_job_run_status({run_id}) para verificar.",
    })


def _dbr_get_job_run_status(run_id: str) -> str:
    run = _client().jobs.get_run(run_id=int(run_id))
    state = run.state
    return json.dumps({
        "run_id": run_id,
        "life_cycle_state": state.life_cycle_state.value if state and state.life_cycle_state else None,
        "result_state": state.result_state.value if state and state.result_state else None,
        "state_message": state.state_message if state else None,
        "start_time": run.start_time,
        "end_time": run.end_time,
    })


def _resolve_cluster_id(cluster_id: str) -> str:
    candidate = cluster_id or settings.databricks_cluster_id
    if candidate:
        try:
            info = _client().clusters.get(cluster_id=candidate)
            if info.state and info.state.value not in ("TERMINATED", "ERROR"):
                return candidate
            logger.warning("Cluster %s está %s, buscando alternativa...", candidate, info.state.value if info.state else "UNKNOWN")
        except DatabricksError:
            logger.warning("Cluster %s não encontrado, buscando alternativa...", candidate)

    clusters = [
        c for c in _client().clusters.list()
        if c.state and c.state.value == "RUNNING"
    ]
    if not clusters:
        if candidate:
            return candidate
        raise ValueError("Nenhum cluster RUNNING encontrado e DATABRICKS_CLUSTER_ID não configurado.")
    return clusters[0].cluster_id


def _dbr_submit_notebook(
    notebook_path: str,
    cluster_id: str = "",
    notebook_params: dict | None = None,
    wait_for_completion: bool = True,
    timeout_seconds: int = 600,
) -> str:
    from databricks.sdk.service.jobs import NotebookTask, SubmitTask

    resolved_cluster = _resolve_cluster_id(cluster_id)
    run_name = notebook_path.rsplit("/", 1)[-1]

    task = SubmitTask(
        task_key="run",
        existing_cluster_id=resolved_cluster,
        notebook_task=NotebookTask(
            notebook_path=notebook_path,
            base_parameters=notebook_params or {},
        ),
    )

    run = _client().jobs.submit(run_name=run_name, tasks=[task])
    run_id = run.run_id

    if not wait_for_completion:
        return json.dumps({"run_id": run_id, "status": "submitted", "cluster_id": resolved_cluster})

    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        status = _client().jobs.get_run(run_id=run_id)
        lcs = status.state.life_cycle_state.value if status.state and status.state.life_cycle_state else "UNKNOWN"
        if lcs in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            rs = status.state.result_state.value if status.state and status.state.result_state else None
            return json.dumps({
                "run_id": run_id,
                "life_cycle_state": lcs,
                "result_state": rs,
                "state_message": status.state.state_message if status.state else None,
                "start_time": status.start_time,
                "end_time": status.end_time,
                "run_page_url": status.run_page_url,
            })
        time.sleep(15)

    elapsed = int(time.monotonic() - start)
    return json.dumps({
        "run_id": run_id,
        "status": "timeout",
        "message": f"Notebook não finalizou em {elapsed}s. Use dbr_get_job_run_status({run_id}) para verificar.",
    })


def _dbr_create_job(
    name: str,
    notebook_path: str = "",
    tasks_config: list | None = None,
    cluster_id: str = "",
    schedule_cron: str = "",
    notebook_params: dict | None = None,
    timeout_seconds: int = 3600,
) -> str:
    """Cria job com uma ou múltiplas tasks (DAG com dependências)."""
    from databricks.sdk.service.jobs import (
        CronSchedule,
        NotebookTask,
        Task,
        TaskDependency,
    )

    resolved_cluster = _resolve_cluster_id(cluster_id)

    if tasks_config:
        job_tasks = []
        for tc in tasks_config:
            deps = [TaskDependency(task_key=d) for d in tc.get("depends_on", [])]
            t = Task(
                task_key=tc["task_key"],
                existing_cluster_id=resolved_cluster,
                notebook_task=NotebookTask(
                    notebook_path=tc["notebook_path"],
                    base_parameters=tc.get("notebook_params") or {},
                ),
                timeout_seconds=tc.get("timeout_seconds", timeout_seconds),
                depends_on=deps if deps else None,
            )
            job_tasks.append(t)
    elif notebook_path:
        job_tasks = [
            Task(
                task_key="main",
                existing_cluster_id=resolved_cluster,
                notebook_task=NotebookTask(
                    notebook_path=notebook_path,
                    base_parameters=notebook_params or {},
                ),
                timeout_seconds=timeout_seconds,
            )
        ]
    else:
        return json.dumps({"error": "Informe notebook_path ou tasks_config."})

    kwargs: dict = {"name": name, "tasks": job_tasks}

    if schedule_cron:
        kwargs["schedule"] = CronSchedule(
            quartz_cron_expression=schedule_cron,
            timezone_id="America/Sao_Paulo",
        )

    job = _client().jobs.create(**kwargs)
    return json.dumps({
        "job_id": job.job_id,
        "name": name,
        "tasks_count": len(job_tasks),
        "task_keys": [t.task_key for t in job_tasks],
        "cluster_id": resolved_cluster,
        "schedule": schedule_cron or "sem schedule (manual)",
        "status": "created",
    })


def _dbr_bundle_validate(target: str = "dev", bundle_path: str = "") -> str:
    import subprocess
    bundle_path = bundle_path or str(Path(settings.local_repo_path or ".") / "databricks_project")
    result = subprocess.run(
        ["databricks", "bundle", "validate", "--target", target],
        capture_output=True, text=True, cwd=bundle_path, timeout=60,
    )
    return json.dumps({
        "target": target,
        "bundle_path": bundle_path,
        "exit_code": result.returncode,
        "stdout": result.stdout[:4000],
        "stderr": result.stderr[:2000],
        "status": "valid" if result.returncode == 0 else "invalid",
    })


def _dbr_bundle_deploy(target: str = "dev", bundle_path: str = "") -> str:
    import subprocess
    if target in ("staging", "prod"):
        return json.dumps({
            "error": f"Deploy para '{target}' requer confirmação explícita do usuário. "
                     "Peça confirmação antes de prosseguir.",
            "status": "blocked",
            "target": target,
        })

    bundle_path = bundle_path or str(Path(settings.local_repo_path or ".") / "databricks_project")
    result = subprocess.run(
        ["databricks", "bundle", "deploy", "--target", target],
        capture_output=True, text=True, cwd=bundle_path, timeout=300,
    )
    return json.dumps({
        "target": target,
        "bundle_path": bundle_path,
        "exit_code": result.returncode,
        "stdout": result.stdout[:4000],
        "stderr": result.stderr[:2000],
        "status": "deployed" if result.returncode == 0 else "failed",
    })


def _dbr_bundle_generate_job(
    job_name: str,
    notebook_path: str = "",
    tasks_config: list | None = None,
    schedule_cron: str = "",
    bundle_path: str = "",
) -> str:
    import yaml

    bundle_path = bundle_path or str(Path(settings.local_repo_path or ".") / "databricks_project")
    resources_dir = Path(bundle_path) / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)

    if tasks_config:
        tasks = []
        for tc in tasks_config:
            task: dict = {
                "task_key": tc["task_key"],
                "notebook_task": {"notebook_path": tc["notebook_path"]},
            }
            if tc.get("depends_on"):
                task["depends_on"] = [{"task_key": d} for d in tc["depends_on"]]
            tasks.append(task)
    elif notebook_path:
        tasks = [{"task_key": "main", "notebook_task": {"notebook_path": notebook_path}}]
    else:
        return json.dumps({"error": "Informe notebook_path ou tasks_config."})

    job_def: dict = {
        "resources": {
            "jobs": {
                job_name: {
                    "name": job_name,
                    "tasks": tasks,
                }
            }
        }
    }

    if schedule_cron:
        job_def["resources"]["jobs"][job_name]["schedule"] = {
            "quartz_cron_expression": schedule_cron,
            "timezone_id": "America/Sao_Paulo",
        }

    file_path = resources_dir / f"{job_name}.job.yml"
    with file_path.open("w") as f:
        yaml.dump(job_def, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return json.dumps({
        "file_path": str(file_path),
        "job_name": job_name,
        "tasks_count": len(tasks),
        "task_keys": [t["task_key"] for t in tasks],
        "schedule": schedule_cron or "sem schedule",
        "status": "generated",
        "next_step": "Use dbr_bundle_validate e dbr_bundle_deploy para validar e implantar.",
    })


def _dbr_list_jobs(name_contains: str = "") -> str:
    kwargs: dict = {}
    if name_contains:
        kwargs["name"] = name_contains
    jobs = [
        {"job_id": j.job_id, "name": j.settings.name if j.settings else ""}
        for j in list(_client().jobs.list(**kwargs))[:50]
    ]
    return json.dumps(jobs)


def _dbr_list_clusters() -> str:
    all_clusters = [
        {
            "cluster_id": c.cluster_id,
            "cluster_name": c.cluster_name or "",
            "state": c.state.value if c.state else "",
        }
        for c in _client().clusters.list()
    ]
    clusters = _truncated_list(all_clusters, "clusters")
    return json.dumps(clusters)


def _dbr_list_warehouses() -> str:
    warehouses = [
        {
            "id": w.id,
            "name": w.name or "",
            "state": w.state.value if w.state else "",
            "cluster_size": w.cluster_size or "",
        }
        for w in _client().warehouses.list()
    ]
    return json.dumps(_truncated_list(warehouses, "warehouses"))


def _dbr_list_volumes(catalog: str = "", schema: str = "") -> str:
    catalog = catalog or settings.databricks_catalog
    schema = schema or settings.databricks_schema
    volumes = [
        {
            "name": v.name,
            "full_name": v.full_name or "",
            "volume_type": v.volume_type.value if v.volume_type else "",
            "storage_location": v.storage_location or "",
        }
        for v in _client().volumes.list(catalog_name=catalog, schema_name=schema)
    ]
    return json.dumps(_truncated_list(volumes, "volumes"))


def _dbr_create_notebook(
    path: str,
    content: str,
    language: str = "PYTHON",
    overwrite: bool = True,
) -> str:
    import base64
    from databricks.sdk.service.workspace import ImportFormat, Language

    lang_map = {
        "PYTHON": Language.PYTHON, "SQL": Language.SQL,
        "SCALA": Language.SCALA, "R": Language.R,
    }
    lang = lang_map.get(language.upper(), Language.PYTHON)
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    _client().workspace.import_(
        path=path,
        content=encoded,
        format=ImportFormat.SOURCE,
        language=lang,
        overwrite=overwrite,
    )
    return json.dumps({"path": path, "status": "created", "language": language})


def _dbr_read_volume_file(path: str, max_bytes: int = 65536) -> str:
    resp = _client().files.download(path)
    content = resp.contents.read(max_bytes)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return json.dumps({"error": "Arquivo binário — não é possível exibir como texto.", "path": path})
    return json.dumps({"path": path, "size": len(content), "content": text})


# ---------------------------------------------------------------------------
# OpenAI function schemas
# ---------------------------------------------------------------------------

DATABRICKS_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "dbr_sql_execute",
            "description": (
                "Executa uma query SQL no Databricks SQL Warehouse. "
                "Use para consultar tabelas Unity Catalog, explorar dados ou rodar DDL. "
                "Se a query demorar mais de 50s, retorna statement_id para polling via dbr_get_statement_status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string", "description": "SQL a executar"},
                    "catalog": {
                        "type": "string",
                        "description": "Catalog Unity Catalog (opcional, usa default se omitido)",
                    },
                    "schema": {"type": "string", "description": "Schema (opcional)"},
                },
                "required": ["statement"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_get_statement_status",
            "description": "Consulta o status de uma query SQL assíncrona pelo statement_id retornado por dbr_sql_execute.",
            "parameters": {
                "type": "object",
                "properties": {
                    "statement_id": {"type": "string", "description": "ID do statement retornado por dbr_sql_execute"},
                },
                "required": ["statement_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_cancel_statement",
            "description": "Cancela uma query SQL em execução pelo statement_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "statement_id": {"type": "string", "description": "ID do statement a cancelar"},
                },
                "required": ["statement_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_catalogs",
            "description": "Lista todos os catalogs Unity Catalog disponíveis no workspace Databricks.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_schemas",
            "description": "Lista schemas dentro de um catalog Unity Catalog. Usa o catalog padrão do settings se omitido.",
            "parameters": {
                "type": "object",
                "properties": {
                    "catalog": {"type": "string", "description": "Nome do catalog (opcional, usa default)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_tables",
            "description": "Lista tabelas em um schema Unity Catalog. Usa catalog/schema padrão do settings se omitidos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "catalog": {"type": "string", "description": "Catalog (opcional, usa default)"},
                    "schema": {"type": "string", "description": "Schema (opcional, usa default)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_get_table_schema",
            "description": (
                "Retorna colunas e tipos de uma tabela Unity Catalog "
                "pelo nome completo (catalog.schema.table)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string", "description": "catalog.schema.table"},
                },
                "required": ["full_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_run_job",
            "description": (
                "Dispara a execução de um Databricks Job pelo job_id. "
                "Com wait_for_completion=true, aguarda o término com polling interno (evita múltiplas chamadas)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "ID numérico do job"},
                    "notebook_params": {
                        "type": "object",
                        "description": "Parâmetros opcionais (key/value) para notebooks tasks",
                    },
                    "wait_for_completion": {
                        "type": "boolean",
                        "description": "Se true, aguarda o job finalizar (polling interno). Default: false.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout em segundos para wait_for_completion. Default: 600.",
                    },
                },
                "required": ["job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_get_job_run_status",
            "description": "Consulta o status de uma execução de job pelo run_id.",
            "parameters": {
                "type": "object",
                "properties": {"run_id": {"type": "string", "description": "ID da execução"}},
                "required": ["run_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_submit_notebook",
            "description": (
                "Executa um notebook Databricks ad-hoc em um cluster existente (jobs.submit). "
                "Ideal para execuções únicas sem criar job permanente. "
                "Com wait_for_completion=true (default), aguarda o término com polling interno."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "notebook_path": {
                        "type": "string",
                        "description": "Caminho do notebook no workspace (ex: /Workspace/Users/.../notebook)",
                    },
                    "cluster_id": {
                        "type": "string",
                        "description": "ID do cluster (opcional, usa DATABRICKS_CLUSTER_ID ou primeiro RUNNING)",
                    },
                    "notebook_params": {
                        "type": "object",
                        "description": "Parâmetros key/value para o notebook (opcional)",
                    },
                    "wait_for_completion": {
                        "type": "boolean",
                        "description": "Se true, aguarda o notebook finalizar (polling interno). Default: true.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout em segundos para wait_for_completion. Default: 600.",
                    },
                },
                "required": ["notebook_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_jobs",
            "description": "Lista jobs do workspace Databricks, opcionalmente filtrando por nome.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_contains": {
                        "type": "string",
                        "description": "Filtro parcial de nome (opcional)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_clusters",
            "description": "Lista clusters ativos e inativos do workspace Databricks.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_warehouses",
            "description": "Lista SQL Warehouses disponíveis no workspace Databricks.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_list_volumes",
            "description": "Lista Volumes do Unity Catalog em um catalog/schema. Usa defaults do settings se omitidos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "catalog": {"type": "string", "description": "Catalog (opcional)"},
                    "schema": {"type": "string", "description": "Schema (opcional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_read_volume_file",
            "description": "Lê o conteúdo de um arquivo armazenado em um Volume Unity Catalog (paridade com OneLake).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Caminho do arquivo no Volume (ex: /Volumes/catalog/schema/volume/file.csv)",
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": "Máximo de bytes a ler. Default: 65536.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_create_notebook",
            "description": (
                "Cria ou atualiza um notebook no workspace Databricks. "
                "Use para persistir lógica de transformação como notebook reutilizável. "
                "O conteúdo deve estar no formato Databricks notebook source (com '# COMMAND ----------' como separador de células)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "notebook_path": {
                        "type": "string",
                        "description": "Caminho no workspace (ex: /Workspace/Users/.../silver/slv_clientes)",
                    },
                    "content": {
                        "type": "string",
                        "description": "Código-fonte do notebook (Databricks notebook source format)",
                    },
                    "language": {
                        "type": "string",
                        "description": "Linguagem: PYTHON, SQL, SCALA, R. Default: PYTHON.",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "Substituir se existir. Default: true.",
                    },
                },
                "required": ["notebook_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_create_job",
            "description": (
                "Cria um Job persistente no Databricks Workflows. "
                "Suporta job simples (1 notebook) ou multi-task com DAG de dependências. "
                "Para multi-task, use tasks_config com depends_on para definir a ordem de execução."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome do job"},
                    "notebook_path": {
                        "type": "string",
                        "description": "Caminho do notebook (para job simples com 1 task). Ignorado se tasks_config for fornecido.",
                    },
                    "tasks_config": {
                        "type": "array",
                        "description": (
                            "Lista de tasks para job multi-task. Cada item: "
                            "{task_key, notebook_path, depends_on?: [task_keys], notebook_params?: {}}. "
                            "Ex: [{task_key: 'slv_contas', notebook_path: '/Workspace/.../slv_contas'}, "
                            "{task_key: 'gld_resumo', notebook_path: '/Workspace/.../gld_resumo', depends_on: ['slv_contas']}]"
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_key": {"type": "string"},
                                "notebook_path": {"type": "string"},
                                "depends_on": {"type": "array", "items": {"type": "string"}},
                                "notebook_params": {"type": "object"},
                            },
                            "required": ["task_key", "notebook_path"],
                        },
                    },
                    "cluster_id": {
                        "type": "string",
                        "description": "Cluster ID (opcional, usa default se omitido)",
                    },
                    "schedule_cron": {
                        "type": "string",
                        "description": "Expressão cron Quartz para agendamento (ex: '0 0 */6 * * ?' para a cada 6h). Opcional — sem schedule = execução manual.",
                    },
                    "notebook_params": {
                        "type": "object",
                        "description": "Parâmetros do notebook (opcional)",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout em segundos. Default: 3600.",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_bundle_validate",
            "description": "Valida um Databricks Asset Bundle. Roda 'databricks bundle validate' e retorna erros/warnings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target do bundle (dev, staging, prod). Default: dev.",
                    },
                    "bundle_path": {
                        "type": "string",
                        "description": "Caminho local do bundle (opcional, detecta automaticamente).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_bundle_deploy",
            "description": (
                "Faz deploy de um Databricks Asset Bundle. Roda 'databricks bundle deploy'. "
                "Deploy direto só é permitido para target 'dev'. "
                "Para staging/prod, requer confirmação explícita do usuário."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target do bundle (dev, staging, prod). Default: dev.",
                    },
                    "bundle_path": {
                        "type": "string",
                        "description": "Caminho local do bundle (opcional, detecta automaticamente).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dbr_bundle_generate_job",
            "description": (
                "Gera um arquivo YAML de definição de job no formato Databricks Asset Bundle. "
                "Suporta job simples (1 notebook) ou multi-task com DAG de dependências. "
                "O arquivo é salvo em resources/<job_name>.job.yml dentro do bundle. "
                "Após gerar, use dbr_bundle_validate e dbr_bundle_deploy para implantar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Nome do job (snake_case)"},
                    "notebook_path": {
                        "type": "string",
                        "description": "Caminho do notebook (para job simples). Ignorado se tasks_config for fornecido.",
                    },
                    "tasks_config": {
                        "type": "array",
                        "description": (
                            "Lista de tasks para job multi-task com DAG. Cada item: "
                            "{task_key, notebook_path, depends_on?: [task_keys]}. "
                            "Tasks sem depends_on rodam em paralelo."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_key": {"type": "string"},
                                "notebook_path": {"type": "string"},
                                "depends_on": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["task_key", "notebook_path"],
                        },
                    },
                    "schedule_cron": {
                        "type": "string",
                        "description": "Expressão cron Quartz (opcional). Ex: '0 0 */6 * * ?'",
                    },
                    "bundle_path": {
                        "type": "string",
                        "description": "Caminho local do bundle (opcional).",
                    },
                },
                "required": ["job_name"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_DISPATCH_MAP = {
    "dbr_sql_execute": lambda a: _dbr_sql_execute(
        a["statement"], a.get("catalog", ""), a.get("schema", "")
    ),
    "dbr_get_statement_status": lambda a: _dbr_get_statement_status(a["statement_id"]),
    "dbr_cancel_statement": lambda a: _dbr_cancel_statement(a["statement_id"]),
    "dbr_list_catalogs": lambda _: _dbr_list_catalogs(),
    "dbr_list_schemas": lambda a: _dbr_list_schemas(a.get("catalog", "")),
    "dbr_list_tables": lambda a: _dbr_list_tables(a.get("catalog", ""), a.get("schema", "")),
    "dbr_get_table_schema": lambda a: _dbr_get_table_schema(a["full_name"]),
    "dbr_run_job": lambda a: _dbr_run_job(
        a["job_id"],
        a.get("notebook_params"),
        a.get("wait_for_completion", False),
        a.get("timeout_seconds", 600),
    ),
    "dbr_get_job_run_status": lambda a: _dbr_get_job_run_status(a["run_id"]),
    "dbr_submit_notebook": lambda a: _dbr_submit_notebook(
        a["notebook_path"],
        a.get("cluster_id", ""),
        a.get("notebook_params"),
        a.get("wait_for_completion", True),
        a.get("timeout_seconds", 600),
    ),
    "dbr_list_jobs": lambda a: _dbr_list_jobs(a.get("name_contains", "")),
    "dbr_list_clusters": lambda _: _dbr_list_clusters(),
    "dbr_list_warehouses": lambda _: _dbr_list_warehouses(),
    "dbr_list_volumes": lambda a: _dbr_list_volumes(a.get("catalog", ""), a.get("schema", "")),
    "dbr_read_volume_file": lambda a: _dbr_read_volume_file(a["path"], a.get("max_bytes", 65536)),
    "dbr_create_notebook": lambda a: _dbr_create_notebook(
        a["notebook_path"], a["content"],
        a.get("language", "PYTHON"), a.get("overwrite", True),
    ),
    "dbr_create_job": lambda a: _dbr_create_job(
        a["name"], a.get("notebook_path", ""),
        a.get("tasks_config"), a.get("cluster_id", ""),
        a.get("schedule_cron", ""), a.get("notebook_params"),
        a.get("timeout_seconds", 3600),
    ),
    "dbr_bundle_validate": lambda a: _dbr_bundle_validate(
        a.get("target", "dev"), a.get("bundle_path", ""),
    ),
    "dbr_bundle_deploy": lambda a: _dbr_bundle_deploy(
        a.get("target", "dev"), a.get("bundle_path", ""),
    ),
    "dbr_bundle_generate_job": lambda a: _dbr_bundle_generate_job(
        a["job_name"], a.get("notebook_path", ""),
        a.get("tasks_config"), a.get("schedule_cron", ""),
        a.get("bundle_path", ""),
    ),
}


def dispatch_databricks(name: str, args: dict) -> str:
    fn = _DISPATCH_MAP.get(name)
    if fn is None:
        return f"Tool Databricks '{name}' não reconhecida."
    try:
        return fn(args)
    except DatabricksError as exc:
        logger.error("Databricks API error [%s]: %s", name, exc)
        return f"Erro Databricks API: {exc}"
    except Exception as exc:
        logger.error("Tool Databricks [%s] exception: %s", name, exc)
        return f"Erro ao executar {name}: {exc}"
