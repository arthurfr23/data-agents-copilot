# Bundles (DABs) — CI/CD & Declarative Automation

**Propósito:** Referência rápida para Declarative Automation Bundles (DABs) — path resolution, deployment, environments e gotchas críticos.

---

## O Que São DABs?

DABs (v0.279.0+) são **declaração pura** de recursos Databricks (jobs, pipelines, dashboards, apps). Nenhum Terraform — native engine apenas.

**Estrutura Mínima:**
```
project/
├── databricks.yml          # Config principal + targets
├── resources/              # Definições de recursos
│   ├── jobs.yml
│   ├── pipelines.yml
│   └── dashboards.yml
└── src/                    # Código/arquivos
    ├── notebooks/
    ├── dashboards/
    └── app/
```

---

## Path Resolution — A Gotcha Mais Comum

**CRÍTICO:** Paths dependem da localização do arquivo.

| Arquivo | Path Format | Exemplo |
|---------|----------|---------|
| `resources/*.yml` | `../src/...` | `../src/dashboards/file.json` |
| `databricks.yml` | `./src/...` | `./src/dashboards/file.json` |
| `resources/nested/job.yml` | `../../src/...` | `../../src/notebooks/etl.py` |

**Por quê?**
- `resources/jobs.yml` está 1 nível fundo → use `../` para voltar à raiz
- `databricks.yml` está na raiz → use `./` para entrar

**Exemplo Correto:**

```yaml
# databricks.yml (root)
resources:
  dashboards:
    my_dashboard:
      file_path: ./src/dashboards/dashboard.lvdash.json  # ✅

# resources/dashboards.yml (1 level deep)
resources:
  dashboards:
    my_dashboard:
      file_path: ../src/dashboards/dashboard.lvdash.json  # ✅
```

**Gotcha:** `../src/...` em `databricks.yml` resulta em "file not found". Erro mais comum.

---

## Validação, Planejamento e Deployment

### Workflow Padrão

```bash
# 1. Validar sintaxe e referências
databricks bundle validate

# 2. Visualizar mudanças (dry-run)
databricks bundle plan

# 3. Deployar para default target
databricks bundle deploy

# 4. Deployar para target específico
databricks bundle deploy -t prod --auto-approve
```

**Output Esperado:**
```
✓ Validating bundle
✓ Bundle content validation completed
✓ Planning deployment
✓ Deployment completed
  Created dashboard: my-dashboard-dev
  Created job: etl-pipeline-dev
```

---

## Targets — Multi-Environment (dev/staging/prod)

Define ambientes no `databricks.yml`:

```yaml
bundle:
  name: my-project

include:
  - resources/*.yml

variables:
  catalog:
    default: dev_catalog
  schema:
    default: dev_schema
  warehouse_id:
    lookup:
      warehouse: "Shared SQL Warehouse"

targets:
  dev:
    default: true
    mode: development
    workspace:
      profile: dev-workspace  # Profile no ~/.databrickscfg
    variables:
      catalog: dev_catalog
      schema: dev_schema

  prod:
    mode: production
    workspace:
      profile: prod-workspace
    variables:
      catalog: prod_catalog
      schema: prod_schema
```

**Usar em recursos:**
```yaml
resources:
  jobs:
    etl:
      name: "[${bundle.target}] ETL Pipeline"  # prod = "[prod] ETL Pipeline"
      tasks:
        - task_key: load
          notebook_task:
            notebook_path: ../src/load.py
```

**Deploy para prod:**
```bash
databricks bundle deploy -t prod
```

---

## Recursos Principais

### Jobs (Exemplo Completo)

```yaml
resources:
  jobs:
    etl_pipeline:
      name: "[${bundle.target}] ETL"
      tasks:
        - task_key: extract
          notebook_task:
            notebook_path: ../src/notebooks/extract.py
          job_cluster_key: shared_cluster

      job_clusters:
        - job_cluster_key: shared_cluster
          new_cluster:
            spark_version: "15.4.x-scala2.12"
            node_type_id: "i3.xlarge"
            num_workers: 2

      schedule:
        quartz_cron_expression: "0 9 * * ?"
        timezone_id: "America/Los_Angeles"

      permissions:
        - level: CAN_VIEW
          group_name: "users"
```

### Dashboards (Exemplo)

```yaml
resources:
  dashboards:
    analytics:
      display_name: "[${bundle.target}] Analytics"
      file_path: ../src/dashboards/analytics.lvdash.json
      warehouse_id: ${var.warehouse_id}
      dataset_catalog: ${var.catalog}      # v0.281.0+
      dataset_schema: ${var.schema}        # v0.281.0+
      permissions:
        - level: CAN_RUN
          group_name: "users"
```

**Gotcha:** `dataset_catalog` e `dataset_schema` adicionados v0.281.0 (janeiro 2026). Versões antigas não suportam.

### Pipelines (SDP)

```yaml
resources:
  pipelines:
    etl:
      name: "[${bundle.target}] SDP ETL"
      target: ${var.catalog}.${var.schema}
      libraries:
        - notebook:
            path: ../src/pipelines/dlt.py
      edition: ADVANCED
```

### SQL Alerts (API v2 Schema)

**CRÍTICO:** Alert schema **difere** de outros recursos.

```yaml
resources:
  sql_alerts:
    data_quality:
      display_name: "Data Quality Check"
      query_id: ${resources.sql_queries.quality_check.id}
      condition:
        op: CUSTOM
        threshold: 1
      notification_config:
        email_notifications:
          - "alerts@company.com"
```

**Gotcha:** Não use `email_notifications` da forma Job. Alert v2 API tem schema específico.

### Apps (Especial)

**Apps NÃO aceitam env vars em `databricks.yml`.** Env vars vão em `app.yaml` no source:

**resources/app.yml:**
```yaml
resources:
  apps:
    my_app:
      name: my-app-${bundle.target}
      source_code_path: ../src/app
```

**src/app/app.yaml:** (Env vars aqui)
```yaml
command:
  - "python"
  - "dash_app.py"

env:
  - name: DATABRICKS_WAREHOUSE_ID
    value: "your-warehouse-id"
  - name: DATABRICKS_CATALOG
    value: "main"
  - name: DATABRICKS_SCHEMA
    value: "my_schema"
```

**Deploy & Start:**
```bash
databricks bundle deploy
databricks bundle run my_app -t dev  # Necessário para iniciar
```

**Ver Logs:**
```bash
databricks apps logs my-app-dev --profile DEFAULT
```

**Gotcha:** Apps requerem `bundle run` APÓS deploy para iniciar. Apenas deploy não sobe a app.

---

## Permissões — Difere por Tipo de Recurso

| Recurso | Níveis Disponíveis |
|---------|-------------------|
| **Jobs** | `CAN_VIEW`, `CAN_MANAGE_RUN`, `CAN_MANAGE` |
| **Dashboards** | `CAN_READ`, `CAN_RUN`, `CAN_EDIT`, `CAN_MANAGE` |
| **Pipelines** | `CAN_VIEW`, `CAN_MANAGE` |
| **SQL Queries** | `CAN_READ`, `CAN_RUN`, `CAN_EDIT`, `CAN_MANAGE` |
| **Volumes** | Use `grants`, não `permissions` |

**Gotcha:** `CAN_MANAGE_RUN` (Jobs-only) não existe para dashboards. Erros silenciosos.

---

## Boas Práticas Críticas

### 1. Path Resolution Checklist
```yaml
# ✅ Em resources/*.yml
file_path: ../src/dashboards/file.json

# ✅ Em databricks.yml
file_path: ./src/dashboards/file.json

# ❌ Em resources/*.yml — ERRADO
file_path: ./src/dashboards/file.json  # Procura ./resources/src/...
```

### 2. Sempre Validar Antes Deploy
```bash
databricks bundle validate
databricks bundle plan  # Revise mudanças
databricks bundle deploy --auto-approve
```

### 3. Variables para Multi-Ambiente
```yaml
variables:
  catalog: { default: "dev" }
  schema: { default: "dev" }

resources:
  jobs:
    job:
      name: "[${bundle.target}] Job"
      tasks:
        - notebook_task:
            notebook_path: ../src/etl.py
            base_parameters:
              catalog: ${var.catalog}
              schema: ${var.schema}
```

### 4. Apps: Env Vars em `app.yaml`, Não em `databricks.yml`
```yaml
# ❌ NÃO funciona em databricks.yml
env:
  WAREHOUSE_ID: "abc"

# ✅ Funciona em src/app/app.yaml
env:
  - name: WAREHOUSE_ID
    value: "abc"
```

### 5. Grupo "admins" Nunca em Permissions
```yaml
permissions:
  - level: CAN_MANAGE
    group_name: "data_engineers"  # ✅

  # ❌ Falha
  # - level: CAN_MANAGE
  #   group_name: "admins"
```

---

## Troubleshooting Comum

| Erro | Causa | Solução |
|------|-------|--------|
| `file not found` | Path incorreto (`./src/` em resources/) | Use `../src/` em resources/*.yml |
| `Cannot find profile X` | Profile não existe em ~/.databrickscfg | Adicionar profile: `databricks configure --profile prod` |
| `Asset bundle contains undefined references` | Variable não definida | Adicionar default em `variables:` section |
| `App not starting` | Deploy sem `bundle run` | Executar `databricks bundle run app_key -t dev` |
| `Permission denied on admins group` | Tentativa modificar "admins" | Remover "admins" de permissions |
| `Dashboard catalog mismatch` | CLI < 0.281.0 sem `dataset_catalog` | Atualizar CLI ou omitir parâmetro |
| `Alert notification failed` | Schema errado (v1 vs v2) | Verificar schema em alerts_guidance.md |

---

## Checklist Implementação

- [ ] Path resolution validado (../src/ em resources/, ./src/ em databricks.yml)
- [ ] Targets dev/prod definidos em databricks.yml
- [ ] Variáveis catalog/schema parametrizadas
- [ ] Profiles configurados (.databrickscfg)
- [ ] Jobs com retry policy e schedule
- [ ] Dashboards com dataset_catalog/dataset_schema (CLI >= 0.281.0)
- [ ] Apps com env vars em app.yaml
- [ ] Permissions corretas por tipo de recurso
- [ ] Grupo "admins" NUNCA em permissions
- [ ] `bundle validate` passa sem erros
- [ ] `bundle plan` revisto antes deploy
