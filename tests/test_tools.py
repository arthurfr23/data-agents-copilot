"""Testes para agents/tools — schemas, dispatcher e registry."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from agents.tools import dispatch_tool, load_tools_for_mcps
from agents.tools.databricks import DATABRICKS_TOOLS, dispatch_databricks
from agents.tools.fabric import FABRIC_TOOLS, dispatch_fabric

# ---------------------------------------------------------------------------
# load_tools_for_mcps
# ---------------------------------------------------------------------------

def test_load_tools_databricks():
    with patch("config.settings.settings") as mock_s:
        mock_s.has_databricks.return_value = True
        mock_s.has_fabric.return_value = False
        mock_s.local_repo_path = ""
        tools = load_tools_for_mcps(["databricks"])
    names = {t["function"]["name"] for t in tools}
    assert "dbr_sql_execute" in names
    assert "dbr_list_catalogs" in names
    assert "dbr_run_job" in names


def test_load_tools_fabric():
    with patch("config.settings.settings") as mock_s:
        mock_s.has_databricks.return_value = False
        mock_s.has_fabric.return_value = True
        mock_s.local_repo_path = ""
        tools = load_tools_for_mcps(["fabric"])
    names = {t["function"]["name"] for t in tools}
    assert "fabric_list_workspaces" in names
    assert "fabric_list_lakehouses" in names
    assert "fabric_run_notebook" in names


def test_load_tools_both():
    with patch("config.settings.settings") as mock_s:
        mock_s.has_databricks.return_value = True
        mock_s.has_fabric.return_value = True
        mock_s.local_repo_path = ""
        tools = load_tools_for_mcps(["databricks", "fabric"])
    assert len(tools) == len(DATABRICKS_TOOLS) + len(FABRIC_TOOLS)


def test_load_tools_unknown_mcp():
    tools = load_tools_for_mcps(["nonexistent"])
    assert tools == []


def test_load_tools_empty():
    assert load_tools_for_mcps([]) == []


# ---------------------------------------------------------------------------
# Tool schema structure
# ---------------------------------------------------------------------------

def test_databricks_tool_schemas_structure():
    for tool in DATABRICKS_TOOLS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        params = fn["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params


def test_fabric_tool_schemas_structure():
    for tool in FABRIC_TOOLS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn


# ---------------------------------------------------------------------------
# dispatch_tool — roteamento global
# ---------------------------------------------------------------------------

def test_dispatch_tool_routes_to_databricks():
    mock_client = MagicMock()
    catalog_obj = MagicMock()
    catalog_obj.name = "main"
    mock_client.catalogs.list.return_value = [catalog_obj]
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_tool("dbr_list_catalogs", "{}")
        assert "main" in result


def test_dispatch_tool_routes_to_fabric():
    with patch("agents.tools.fabric._get_token", return_value="fake_token"), \
         patch("agents.tools.fabric._get") as mock_get:
        mock_get.return_value = {"value": [{"id": "ws1", "displayName": "WS 1"}]}
        result = dispatch_tool("fabric_list_workspaces", "{}")
        assert "ws1" in result


def test_dispatch_tool_unknown():
    result = dispatch_tool("nonexistent_tool", "{}")
    assert "não encontrada" in result


# ---------------------------------------------------------------------------
# dispatch_databricks
# ---------------------------------------------------------------------------

def test_dbr_sql_execute_success():
    mock_client = MagicMock()
    col1 = MagicMock(); col1.name = "id"
    col2 = MagicMock(); col2.name = "name"
    resp = MagicMock()
    resp.status.state = MagicMock(value="SUCCEEDED")
    # Make it compare equal to StatementState.SUCCEEDED
    from databricks.sdk.service.sql import StatementState
    resp.status.state = StatementState.SUCCEEDED
    resp.manifest.schema.columns = [col1, col2]
    resp.result.data_array = [["1", "Alice"], ["2", "Bob"]]
    mock_client.statement_execution.execute_statement.return_value = resp
    with patch("agents.tools.databricks._client", return_value=mock_client), \
         patch("agents.tools.databricks.settings") as mock_settings:
        mock_settings.databricks_sql_warehouse_id = "wh123"
        mock_settings.databricks_catalog = "main"
        mock_settings.databricks_schema = "default"
        result = dispatch_databricks("dbr_sql_execute", {"statement": "SELECT 1"})
    data = json.loads(result)
    assert data["columns"] == ["id", "name"]
    assert len(data["rows"]) == 2


def test_dbr_sql_execute_no_warehouse():
    with patch("agents.tools.databricks.settings") as mock_settings:
        mock_settings.databricks_sql_warehouse_id = ""
        result = dispatch_databricks("dbr_sql_execute", {"statement": "SELECT 1"})
    assert "DATABRICKS_SQL_WAREHOUSE_ID" in result


def test_dbr_list_catalogs():
    mock_client = MagicMock()
    c1 = MagicMock(); c1.name = "main"
    c2 = MagicMock(); c2.name = "dev"
    mock_client.catalogs.list.return_value = [c1, c2]
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_list_catalogs", {})
    assert json.loads(result) == ["main", "dev"]


def test_dbr_list_schemas():
    mock_client = MagicMock()
    s1 = MagicMock(); s1.name = "bronze"
    s2 = MagicMock(); s2.name = "silver"
    mock_client.schemas.list.return_value = [s1, s2]
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_list_schemas", {"catalog": "main"})
    assert "bronze" in json.loads(result)


def test_dbr_list_tables():
    mock_client = MagicMock()
    t = MagicMock()
    t.name = "orders"
    t.table_type = MagicMock(value="MANAGED")
    t.full_name = "main.sales.orders"
    mock_client.tables.list.return_value = [t]
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_list_tables", {"catalog": "main", "schema": "sales"})
    tables = json.loads(result)
    assert tables[0]["name"] == "orders"


def test_dbr_get_table_schema():
    mock_client = MagicMock()
    col = MagicMock()
    col.name = "id"; col.type_text = "bigint"; col.nullable = False
    table = MagicMock()
    table.columns = [col]
    table.properties = {}
    mock_client.tables.get.return_value = table
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_get_table_schema", {"full_name": "main.sales.orders"})
    data = json.loads(result)
    assert data["columns"][0]["name"] == "id"


def test_dbr_run_job():
    mock_client = MagicMock()
    run = MagicMock()
    run.run_id = 42; run.number_in_job = 1
    mock_client.jobs.run_now.return_value = run
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_run_job", {"job_id": "123"})
    assert json.loads(result)["run_id"] == 42


def test_dbr_get_job_run_status():
    mock_client = MagicMock()
    run = MagicMock()
    run.state.life_cycle_state = MagicMock(value="TERMINATED")
    run.state.result_state = MagicMock(value="SUCCESS")
    run.state.state_message = ""
    run.start_time = 1000; run.end_time = 2000
    mock_client.jobs.get_run.return_value = run
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_get_job_run_status", {"run_id": "99"})
    data = json.loads(result)
    assert data["life_cycle_state"] == "TERMINATED"


def test_dbr_list_jobs():
    mock_client = MagicMock()
    job = MagicMock()
    job.job_id = 1; job.settings.name = "etl_job"
    mock_client.jobs.list.return_value = [job]
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_list_jobs", {})
    assert json.loads(result)[0]["name"] == "etl_job"


def test_dbr_list_clusters():
    mock_client = MagicMock()
    cluster = MagicMock()
    cluster.cluster_id = "cl1"; cluster.cluster_name = "main"
    cluster.state = MagicMock(value="RUNNING")
    mock_client.clusters.list.return_value = [cluster]
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_list_clusters", {})
    assert json.loads(result)[0]["state"] == "RUNNING"


def test_dispatch_databricks_api_error():
    from databricks.sdk.errors import DatabricksError
    with patch("agents.tools.databricks._client") as mock_client:
        mock_client.return_value.catalogs.list.side_effect = DatabricksError("Unauthorized")
        result = dispatch_databricks("dbr_list_catalogs", {})
    assert "Erro" in result


def test_dispatch_databricks_unknown_tool():
    result = dispatch_databricks("dbr_nonexistent", {})
    assert "não reconhecida" in result


def test_dbr_list_schemas_default_catalog():
    mock_client = MagicMock()
    s1 = MagicMock(); s1.name = "bronze"
    mock_client.schemas.list.return_value = [s1]
    with patch("agents.tools.databricks._client", return_value=mock_client), \
         patch("agents.tools.databricks.settings") as mock_s:
        mock_s.databricks_catalog = "fallback_catalog"
        result = dispatch_databricks("dbr_list_schemas", {})
    mock_client.schemas.list.assert_called_with(catalog_name="fallback_catalog")
    assert "bronze" in result


def test_dbr_list_tables_default_catalog_schema():
    mock_client = MagicMock()
    t = MagicMock(); t.name = "tbl"; t.table_type = MagicMock(value="MANAGED"); t.full_name = "c.s.tbl"
    mock_client.tables.list.return_value = [t]
    with patch("agents.tools.databricks._client", return_value=mock_client), \
         patch("agents.tools.databricks.settings") as mock_s:
        mock_s.databricks_catalog = "cat"
        mock_s.databricks_schema = "sch"
        result = dispatch_databricks("dbr_list_tables", {})
    mock_client.tables.list.assert_called_with(catalog_name="cat", schema_name="sch")
    assert "tbl" in result


def test_dbr_list_warehouses():
    mock_client = MagicMock()
    w = MagicMock(); w.id = "wh1"; w.name = "Starter"; w.state = MagicMock(value="RUNNING"); w.cluster_size = "2X-Small"
    mock_client.warehouses.list.return_value = [w]
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_list_warehouses", {})
    assert json.loads(result)[0]["id"] == "wh1"


def test_dbr_list_volumes():
    mock_client = MagicMock()
    v = MagicMock(); v.name = "raw_files"; v.full_name = "main.bronze.raw_files"
    v.volume_type = MagicMock(value="MANAGED"); v.storage_location = "s3://bucket/path"
    mock_client.volumes.list.return_value = [v]
    with patch("agents.tools.databricks._client", return_value=mock_client), \
         patch("agents.tools.databricks.settings") as mock_s:
        mock_s.databricks_catalog = "main"
        mock_s.databricks_schema = "bronze"
        result = dispatch_databricks("dbr_list_volumes", {})
    assert json.loads(result)[0]["name"] == "raw_files"


def test_dbr_get_statement_status():
    mock_client = MagicMock()
    from databricks.sdk.service.sql import StatementState
    resp = MagicMock()
    resp.status.state = StatementState.SUCCEEDED
    col = MagicMock(); col.name = "x"
    resp.manifest.schema.columns = [col]
    resp.result.data_array = [["1"]]
    mock_client.statement_execution.get_statement.return_value = resp
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_get_statement_status", {"statement_id": "stmt1"})
    data = json.loads(result)
    assert data["columns"] == ["x"]


def test_dbr_cancel_statement():
    mock_client = MagicMock()
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_cancel_statement", {"statement_id": "stmt1"})
    data = json.loads(result)
    assert data["status"] == "cancelled"
    mock_client.statement_execution.cancel_execution.assert_called_with(statement_id="stmt1")


def test_dbr_sql_execute_returns_statement_id_on_pending():
    mock_client = MagicMock()
    resp = MagicMock()
    resp.status.state = MagicMock(value="PENDING")
    resp.status.state.__eq__ = lambda self, other: False  # not SUCCEEDED
    resp.status.error = None
    resp.statement_id = "stmt-abc"
    mock_client.statement_execution.execute_statement.return_value = resp
    with patch("agents.tools.databricks._client", return_value=mock_client), \
         patch("agents.tools.databricks.settings") as mock_s:
        mock_s.databricks_sql_warehouse_id = "wh1"
        mock_s.databricks_catalog = "main"
        mock_s.databricks_schema = "default"
        result = dispatch_databricks("dbr_sql_execute", {"statement": "SELECT 1"})
    data = json.loads(result)
    assert data["statement_id"] == "stmt-abc"


def test_dbr_tool_count():
    assert len(DATABRICKS_TOOLS) == 20


def test_dbr_submit_notebook_no_wait():
    mock_client = MagicMock()
    run_resp = MagicMock()
    run_resp.run_id = 12345
    mock_client.jobs.submit.return_value = run_resp
    with patch("agents.tools.databricks._client", return_value=mock_client), \
         patch("agents.tools.databricks.settings") as mock_s:
        mock_s.databricks_cluster_id = "cluster-abc"
        result = dispatch_databricks("dbr_submit_notebook", {
            "notebook_path": "/Workspace/Users/test/notebook",
            "wait_for_completion": False,
        })
    data = json.loads(result)
    assert data["run_id"] == 12345
    assert data["status"] == "submitted"
    assert data["cluster_id"] == "cluster-abc"
    mock_client.jobs.submit.assert_called_once()


def test_dbr_submit_notebook_with_explicit_cluster():
    mock_client = MagicMock()
    run_resp = MagicMock()
    run_resp.run_id = 99999
    mock_client.jobs.submit.return_value = run_resp
    with patch("agents.tools.databricks._client", return_value=mock_client), \
         patch("agents.tools.databricks.settings") as mock_s:
        mock_s.databricks_cluster_id = ""
        result = dispatch_databricks("dbr_submit_notebook", {
            "notebook_path": "/Workspace/Users/test/nb",
            "cluster_id": "explicit-cluster-id",
            "wait_for_completion": False,
        })
    data = json.loads(result)
    assert data["cluster_id"] == "explicit-cluster-id"


def test_dbr_submit_notebook_resolve_running_cluster():
    mock_client = MagicMock()
    cluster = MagicMock()
    cluster.cluster_id = "running-123"
    cluster.state = MagicMock()
    cluster.state.value = "RUNNING"
    mock_client.clusters.list.return_value = [cluster]
    run_resp = MagicMock()
    run_resp.run_id = 55555
    mock_client.jobs.submit.return_value = run_resp
    with patch("agents.tools.databricks._client", return_value=mock_client), \
         patch("agents.tools.databricks.settings") as mock_s:
        mock_s.databricks_cluster_id = ""
        result = dispatch_databricks("dbr_submit_notebook", {
            "notebook_path": "/Workspace/Users/test/nb",
            "wait_for_completion": False,
        })
    data = json.loads(result)
    assert data["cluster_id"] == "running-123"


def test_dbr_submit_notebook_schema_exists():
    names = [t["function"]["name"] for t in DATABRICKS_TOOLS]
    assert "dbr_submit_notebook" in names
    schema = next(t for t in DATABRICKS_TOOLS if t["function"]["name"] == "dbr_submit_notebook")
    assert "notebook_path" in schema["function"]["parameters"]["required"]


# ---------------------------------------------------------------------------
# dispatch_fabric
# ---------------------------------------------------------------------------

def test_fabric_list_workspaces():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get") as mock_get:
        mock_get.return_value = {"value": [{"id": "ws1", "displayName": "Prod WS"}]}
        result = dispatch_fabric("fabric_list_workspaces", {})
    assert json.loads(result)[0]["id"] == "ws1"


def test_dbr_create_notebook():
    mock_client = MagicMock()
    with patch("agents.tools.databricks._client", return_value=mock_client):
        result = dispatch_databricks("dbr_create_notebook", {
            "notebook_path": "/Workspace/Users/test/my_notebook",
            "content": "# Databricks notebook source\nprint('hello')",
        })
    data = json.loads(result)
    assert data["status"] == "created"
    assert data["path"] == "/Workspace/Users/test/my_notebook"
    mock_client.workspace.import_.assert_called_once()


def test_dbr_create_notebook_schema_exists():
    names = [t["function"]["name"] for t in DATABRICKS_TOOLS]
    assert "dbr_create_notebook" in names
    schema = next(t for t in DATABRICKS_TOOLS if t["function"]["name"] == "dbr_create_notebook")
    assert "notebook_path" in schema["function"]["parameters"]["required"]
    assert "content" in schema["function"]["parameters"]["required"]


def test_fabric_list_items():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get") as mock_get:
        mock_get.return_value = {"value": [{"id": "nb1", "displayName": "NB1", "type": "Notebook"}]}
        result = dispatch_fabric("fabric_list_items", {"workspace_id": "ws1"})
    assert json.loads(result)[0]["type"] == "Notebook"


def test_fabric_list_lakehouses():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get") as mock_get, \
         patch("agents.tools.fabric.settings") as mock_s:
        mock_s.fabric_workspace_id = "ws1"
        mock_get.return_value = {"value": [{"id": "lh1", "displayName": "Bronze"}]}
        result = dispatch_fabric("fabric_list_lakehouses", {})
    assert "lh1" in result


def test_fabric_get_lakehouse_tables():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get") as mock_get:
        mock_get.return_value = {"data": [{"name": "orders", "type": "Managed", "format": "Delta"}]}
        result = dispatch_fabric(
            "fabric_get_lakehouse_tables",
            {"workspace_id": "ws1", "lakehouse_id": "lh1"},
        )
    assert json.loads(result)[0]["name"] == "orders"


def test_fabric_run_notebook():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._post") as mock_post:
        mock_post.return_value = {"id": "job1"}
        result = dispatch_fabric("fabric_run_notebook", {"workspace_id": "ws1", "item_id": "nb1"})
    assert json.loads(result)["id"] == "job1"


def test_fabric_get_job_instance():
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get") as mock_get:
        mock_get.return_value = {
            "id": "ji1", "status": "Completed",
            "startTimeUtc": "2024-01-01T00:00:00Z",
            "endTimeUtc": "2024-01-01T01:00:00Z",
        }
        result = dispatch_fabric(
            "fabric_get_job_instance",
            {"workspace_id": "ws1", "item_id": "nb1", "job_instance_id": "ji1"},
        )
    assert json.loads(result)["status"] == "Completed"


def test_dispatch_fabric_http_error():
    http_err = requests.HTTPError(response=MagicMock(text="Forbidden"))
    with patch("agents.tools.fabric._get_token", return_value="tok"), \
         patch("agents.tools.fabric._get", side_effect=http_err):
        result = dispatch_fabric("fabric_list_workspaces", {})
    assert "Erro Fabric API" in result


def test_dispatch_fabric_unknown_tool():
    result = dispatch_fabric("fabric_nonexistent", {})
    assert "não reconhecida" in result


# ---------------------------------------------------------------------------
# Token cache
# ---------------------------------------------------------------------------

def test_fabric_token_no_credentials():
    from agents.tools.fabric import _get_token
    with patch("agents.tools.fabric.settings") as mock_s:
        mock_s.azure_tenant_id = ""
        mock_s.azure_client_id = ""
        with pytest.raises(RuntimeError, match="AZURE_TENANT_ID"):
            _get_token()
