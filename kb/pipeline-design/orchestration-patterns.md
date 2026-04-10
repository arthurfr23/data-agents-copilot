# Padrões de Orquestração: Jobs, Workflows, Data Factory, DABs

Comparação de ferramentas de orquestração para pipelines cross-platform.

---

## Matriz de Decisão Estratégica

| Critério | Databricks Jobs | Fabric Data Pipelines | DABs (Bundles) | Data Factory |
|----------|-----------------|----------------------|----------------|--------------|
| **Multi-task DAG** | ✓ Nativo | ✓ Nativo | ✓ Recomendado | ✓ Nativo |
| **Triggers**  | Cron, table update, file arrival | Cron, manual | Cron, CI/CD | Cron, event grid |
| **Linguagem** | Python, SQL, Scala, R | Python, SQL | YAML declarativo | JSON, UI |
| **Versionamento** | API/SDK | UI ou JSON | ✓ Git (recomendado) | Git (recomendado) |
| **Cross-platform** | Databricks only | Fabric only | Databricks + API | ✓ Multi-cloud |
| **Curva aprendizado** | Média | Baixa | Baixa | Alta |
| **Deploy via code** | SDK/CLI | SDK/UI | ✓ Recomendado | ARM/Bicep |
| **Custo** | Créditos Databricks | Créditos Fabric | Créditos Databricks | Azure + Data Factory |

---

## 1. Databricks Jobs (Multi-Task DAG)

### Quando usar
- Pipelines puramente Databricks
- Múltiplas tasks com dependências complexas
- Integração com Unity Catalog
- Monitoramento nativo

### Estrutura (DABs + YAML)

```yaml
# resources/jobs.yml
resources:
  jobs:
    gold_pipeline:
      name: "Gold Pipeline - Vendas"
      description: "Orquestra Bronze → Silver → Gold"

      job_clusters:
        - job_cluster_key: shared_compute
          new_cluster:
            spark_version: "15.4.x-scala2.12"
            node_type_id: "i3.xlarge"
            num_workers: 2
            spark_conf:
              spark.speculation: "true"

      tasks:
        # Task 1: Validação de dados na Silver
        - task_key: validate_silver
          sql_task:
            alert:
              alert_id: "alert-silver-quality"
              pause_subscriptions: false
            warehouse_id: "abc123"

        # Task 2: Construir Gold (depende de validação)
        - task_key: build_gold
          depends_on:
            - task_key: validate_silver
          run_if: "ALL_SUCCESS"
          notebook_task:
            notebook_path: "../src/gold_build"
            base_parameters:
              catalog: "prod"
              schema: "gold"
          job_cluster_key: shared_compute

        # Task 3: Data quality (depois do Gold)
        - task_key: quality_check
          depends_on:
            - task_key: build_gold
          run_if: "ALL_SUCCESS"
          sql_task:
            warehouse_id: "abc123"
            sql_file: "../queries/gold_quality.sql"

        # Task 4: Notificação (executa sempre)
        - task_key: notify
          depends_on:
            - task_key: quality_check
          run_if: "ALL_DONE"
          notebook_task:
            notebook_path: "../src/notify"

      schedule:
        quartz_cron_expression: "0 2 * * ?"  # 2AM UTC
        timezone_id: "UTC"
        pause_status: "UNPAUSED"

      notification_settings:
        no_alert_for_skipped_runs: false
        no_alert_for_successful_runs: false
        alert_on_failure:
          - email_address: "data-team@company.com"
```

### Monitoramento

```python
# Python SDK: Monitorar execução
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import ListJobsRequest

w = WorkspaceClient()

# Listar jobs
for job in w.jobs.list(name_contains="Gold Pipeline"):
    print(f"Job ID: {job.job_id}, Name: {job.job_name}")

# Get última execução
runs = w.jobs.list_runs(job_id=123, limit=1)
for run in runs:
    print(f"Run ID: {run.run_id}")
    print(f"State: {run.state}")
    print(f"Start time: {run.start_time}")
    print(f"End time: {run.end_time}")

    # Task details
    for task_run in run.tasks:
        print(f"  Task: {task_run.task_key}, State: {task_run.state}")
```

### run_if Conditions

```yaml
tasks:
  - task_key: extract
    # ...

  - task_key: transform
    depends_on:
      - task_key: extract
    run_if: "ALL_SUCCESS"  # Executa apenas se extract sucedeu

  - task_key: load
    depends_on:
      - task_key: transform
    run_if: "AT_LEAST_ONE_SUCCESS"  # Executa se pelo menos 1 dep sucedeu

  - task_key: cleanup
    depends_on:
      - task_key: load
    run_if: "ALL_DONE"  # Executa sempre (sucesso ou falha)
```

---

## 2. Fabric Data Pipelines (UI-First)

### Quando usar
- Pipelines Fabric + Databricks (via REST)
- Usuários menos técnicos
- Copy activities simples

### Estrutura

```json
{
  "name": "gold_pipeline_fabric",
  "activities": [
    {
      "name": "CheckSourceData",
      "type": "Lookup",
      "typeProperties": {
        "source": {
          "type": "QueryActivity",
          "query": "SELECT COUNT(*) as cnt FROM silver_vendas"
        }
      }
    },
    {
      "name": "TransformGold",
      "type": "ExecuteNotebook",
      "dependsOn": [{ "activity": "CheckSourceData" }],
      "typeProperties": {
        "notebook": "/gold_vendas",
        "workspace": "my-workspace"
      }
    },
    {
      "name": "NotifySuccess",
      "type": "WebActivity",
      "dependsOn": [{ "activity": "TransformGold" }],
      "typeProperties": {
        "url": "https://prod-XX.logic.azure.com:443/triggers/webhook/...",
        "method": "POST",
        "body": {
          "status": "SUCCESS",
          "timestamp": "@utcnow()"
        }
      }
    }
  ],
  "schedules": [
    {
      "frequency": "Day",
      "interval": 1,
      "startTime": "2026-01-01T02:00:00Z"
    }
  ]
}
```

### Chamar Databricks Job via Fabric

```json
{
  "name": "TriggerDatabricksJob",
  "type": "ExecuteActivity",
  "typeProperties": {
    "linkedServiceName": "DatabricksLinkedService",
    "command": {
      "type": "Python",
      "script": "databricks jobs run-now --job-id 123 --wait"
    }
  }
}
```

---

## 3. DABs (Declarative Automation Bundles) — Recomendado

### Por que DABs
- ✓ Versionamento completo em Git
- ✓ Multi-environment (dev, staging, prod)
- ✓ Deploy via CLI nativo (sem Terraform a partir de v0.279.0)
- ✓ Validação automática

### Estrutura Completa

```yaml
# databricks.yml
bundle:
  name: data-agents-prod
  target: prod

variables:
  environment:
    default: dev
  catalog:
    default: dev_catalog

targets:
  dev:
    variables:
      environment: dev
      catalog: dev_catalog

  prod:
    variables:
      environment: prod
      catalog: prod_catalog

resources:
  pipelines:
    bronze_ingestion:
      name: "[${var.environment}] Bronze Ingestion"
      configuration:
        cloudFiles.schemaInferenceMode: "addNewColumns"
      cluster:
        num_workers: 2
        spark_version: "15.4.x"

  jobs:
    gold_build:
      name: "[${var.environment}] Gold Build Pipeline"
      tasks:
        - task_key: build_gold_dim
          pipeline_task:
            pipeline_id: ${resources.pipelines.bronze_ingestion.id}

        - task_key: build_gold_facts
          depends_on:
            - task_key: build_gold_dim
          notebook_task:
            notebook_path: ../src/gold_facts

      schedule:
        quartz_cron_expression: "0 2 * * ?"
        timezone_id: "UTC"
```

### Deploy Workflow (CLI v0.279.0+)

```bash
# 1. Validar antes de implantar
databricks bundle validate

# 2. Ver plano de mudanças (JSON para CI/CD)
databricks bundle plan -o json > plan.json

# 3. Deploy nativo (sem Terraform)
databricks bundle deploy

# 4. Executar job
databricks bundle run gold_build

# 5. Destruir recursos
databricks bundle destroy
```

---

## 4. Azure Data Factory (Cross-Platform)

### Quando usar
- Orquestração multi-cloud (Azure + AWS + GCP)
- Copy activities em massa
- Integração com Power BI / Synapse

### Padrão: Data Factory → Databricks + Fabric

```json
{
  "name": "CrossPlatformETL",
  "activities": [
    {
      "name": "CopyFromDataLake",
      "type": "Copy",
      "inputs": [
        {
          "referenceName": "AzureBlobSource",
          "type": "DatasetReference"
        }
      ],
      "outputs": [
        {
          "referenceName": "DatabricksDestination",
          "type": "DatasetReference"
        }
      ]
    },
    {
      "name": "RunDatabricksJob",
      "type": "WebActivity",
      "dependsOn": [{ "activity": "CopyFromDataLake" }],
      "typeProperties": {
        "url": "https://databricks.com/api/2.1/jobs/run-now",
        "method": "POST",
        "headers": {
          "Authorization": "Bearer @{linkedService().accessToken}"
        },
        "body": {
          "job_id": 123
        }
      }
    }
  ]
}
```

---

## Comparação Detalhada por Cenário

### Cenário A: Pipeline Databricks puro (Bronze → Silver → Gold)
**Recomendado:** DABs (ou Databricks Jobs direto)
```yaml
# Um pipeline SDP que faz tudo
resources:
  pipelines:
    medallion:
      # Todos os 3 layers em 1 pipeline
      transformations: "sql/**"
```

### Cenário B: Fabric → Databricks → Fabric (round-trip)
**Recomendado:** Data Factory + OneLake Shortcuts
1. Fabric exporta dados
2. Data Factory orquestra a movimentação
3. Databricks processa via Auto Loader
4. Databricks escreve em ABFSS
5. Fabric consome via shortcut

### Cenário C: Monitoramento contínuo + Alertas
**Recomendado:** Databricks Jobs + SQL Alert Tasks
```yaml
tasks:
  - task_key: data_quality_check
    sql_task:
      alert:
        alert_id: "<uuid>"
  - task_key: downstream_task
    depends_on:
      - task_key: data_quality_check
    run_if: "ALL_SUCCESS"
```

### Cenário D: Múltiplos ambientes (dev → staging → prod)
**Recomendado:** DABs com targets
```yaml
targets:
  dev: { variables: { env: dev } }
  staging: { variables: { env: staging } }
  prod: { variables: { env: prod } }

# Deploy com: databricks bundle deploy -t prod
```

---

## Monitoramento Unificado

### Databricks: System Tables para Auditoria

```sql
-- Ver execuções de job
SELECT
  job_id,
  run_id,
  state,
  start_time,
  end_time,
  duration_ms
FROM system.jobs.job_run
WHERE job_id = 123
ORDER BY end_time DESC
LIMIT 10;

-- Ver eventos de acesso (Security)
SELECT
  timestamp,
  user_name,
  action,
  object_id
FROM system.access.audit
WHERE object_type = 'job'
ORDER BY timestamp DESC;
```

### Fabric: Activity Monitoring

```python
# Python SDK: Monitorar Fabric pipelines
from azure.identity import DefaultAzureCredential
from azure.monitor.query import MetricsQueryClient

credential = DefaultAzureCredential()
client = MetricsQueryClient(credential)

# Query métricas de Activity
metrics = client.query_resource(
    resource_id="/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.DataFactory/factories/{name}",
    metric_names=["ActivityRuns", "PipelineRuns"],
    granularity="PT1M"
)
```

---

## Checklist de Seleção

### Use Databricks Jobs se:
- [ ] Pipeline é 100% Databricks
- [ ] Precisa de Unity Catalog + governança
- [ ] Multi-task DAG simples

### Use DABs se:
- [ ] Versionar em Git é obrigatório
- [ ] Multi-ambiente (dev, staging, prod)
- [ ] Deploy via CLI + CI/CD (GitHub Actions, etc)

### Use Fabric Data Pipelines se:
- [ ] Usuários Fabric first
- [ ] Copy activities dominam
- [ ] Integração Power BI necessária

### Use Data Factory se:
- [ ] Cross-platform (Databricks + Fabric + Data Lake)
- [ ] Orquestração complexa multi-cloud
- [ ] Integração Synapse necessária
