# Jobs & Workflows — Padrões Multi-Task

**Propósito:** Referência rápida para Jobs multi-task, DAGs, retry policies, scheduling e idempotência.

---

## Arquitetura: Jobs Multi-Task DAG

Jobs orquestram múltiplas tarefas com dependências explícitas.

**Estrutura básica:**
```yaml
resources:
  jobs:
    etl_pipeline:
      name: "ETL Pipeline — {{bundle.target}}"
      tasks:
        - task_key: extract
          notebook_task:
            notebook_path: ../src/extract.py

        - task_key: transform
          depends_on:
            - task_key: extract
          notebook_task:
            notebook_path: ../src/transform.py

        - task_key: load
          depends_on:
            - task_key: transform
          run_if: ALL_SUCCESS
          notebook_task:
            notebook_path: ../src/load.py
```

---

## Tipos de Tarefas (Task Types)

| Tipo | Uso | Exemplo |
|------|-----|---------|
| `notebook_task` | Executar notebook (.py/.sql/.scala) | ETL, exploração |
| `spark_python_task` | Script Python (não notebook) | PySpark direto |
| `python_wheel_task` | Pacote Python compilado | ML, distribuído |
| `sql_task` | Query SQL ou arquivo .sql | Queries diretas |
| `dbt_task` | Transformações dbt | Modelos dbt |
| `pipeline_task` | Trigger SDP/DLT pipeline | Pipelines declarativas |
| `run_job_task` | Chamar outro job | Orquestração hierárquica |
| `for_each_task` | Loop parametrizado | Processamento por lote |
| `spark_jar_task` | Execute JAR Scala/Java | Código compilado |

**Exemplo — Python Wheel Task:**
```yaml
tasks:
  - task_key: ml_train
    python_wheel_task:
      package_name: "ml_package"
      entry_point: "train"
      parameters: ["--epochs", "50"]
```

---

## Dependências: run_if Conditions

Controle o fluxo com 6 condições:

| Condição | Executado Quando |
|----------|-----------------|
| `ALL_SUCCESS` (padrão) | Todas as dependências sucesso |
| `ALL_DONE` | Todas completadas (sucesso OU falha) |
| `AT_LEAST_ONE_SUCCESS` | Pelo menos uma sucesso |
| `NONE_FAILED` | Nenhuma falhou (sucesso ou skipped) |
| `ALL_FAILED` | Todas falharam |
| `AT_LEAST_ONE_FAILED` | Pelo menos uma falhou |

**Exemplo — Tratamento de Falha:**
```yaml
tasks:
  - task_key: extract
    notebook_task:
      notebook_path: ../src/extract.py

  - task_key: retry_extract
    depends_on:
      - task_key: extract
    run_if: AT_LEAST_ONE_FAILED  # Se extract falhar
    notebook_task:
      notebook_path: ../src/extract_fallback.py

  - task_key: transform
    depends_on:
      - task_key: retry_extract
    run_if: AT_LEAST_ONE_SUCCESS  # Se retry sucesso
    notebook_task:
      notebook_path: ../src/transform.py
```

**Gotcha:** `run_if` é avaliado APÓS todas dependências completarem. Sem `ALL_DONE`, não espera falhas.

---

## Retry Policy — Exponential Backoff

Sempre configure retry para resiliência:

```yaml
resources:
  jobs:
    pipeline:
      tasks:
        - task_key: extract
          max_retries: 3
          retry_on_timeout: true
          timeout_seconds: 3600  # 1 hora
          notebook_task:
            notebook_path: ../src/extract.py
```

**Padrão recomendado:**
- `max_retries: 2` (3 tentativas totais)
- `retry_on_timeout: true`
- `timeout_seconds: 3600` (padrão para ETL)

**Exponential backoff (automático):**
- Tentativa 1: falha imediata
- Tentativa 2: espera ~30s
- Tentativa 3: espera ~1min

**Gotcha:** Timeout é por task, não por job inteiro. Configure para cada tarefa longa.

---

## Scheduling: Cron, File Arrival, Table Updates

### 1. Cron Schedule (Recomendado)

```yaml
trigger:
  periodic:
    interval: 1
    frequency: DAYS

# OU mais controle com Quartz Cron
schedule:
  quartz_cron_expression: "0 9 * * ?"  # 9 AM diariamente
  timezone_id: "America/Los_Angeles"
```

**Exemplos Quartz Cron:**
- `0 9 * * ?` — 9 AM todos os dias
- `0 9 * * 1-5` — 9 AM weekdays
- `0 9 1 * ?` — 9 AM primeiro dia do mês
- `0 0,12 * * ?` — 00:00 e 12:00 diariamente

### 2. File Arrival Trigger

```yaml
trigger:
  file_arrival:
    min_time_between_triggers_seconds: 3600  # Aguardar 1 hora
    url: "s3://my-bucket/incoming/data/"
```

**Gotcha:** URL deve ter permissões da workspace. Padrão = qualquer arquivo novo.

### 3. Table Update Trigger

```yaml
trigger:
  table_update:
    table_names:
      - "main.raw.incoming_data"
    min_time_between_triggers_seconds: 600  # Min 10 min
```

**Gotcha:** Requer Unity Catalog table. Hive_metastore não suporta.

### 4. Manual (Ad-Hoc)

```yaml
# Sem trigger section — executar manualmente
trigger: {}  # ou omitir
```

**Executar via SDK:**
```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
run = w.jobs.run_now(
    job_id=12345,
    idempotency_token="my-unique-token-123"  # Evitar duplicatas
)
```

---

## Idempotência: Tokens & Identificação

Use `idempotency_token` para evitar execuções duplicadas:

```python
import uuid

token = f"etl-run-{date.today()}"  # Ou UUID único

run = w.jobs.run_now(
    job_id=job_id,
    idempotency_token=token
)

# Se chamar novamente com mesmo token, não cria nova run
```

**Gotcha:** Token é válido por 24 horas. Tokens idênticos retornam mesma run.

---

## Notificações de Alerta

Configure alertas para falhas/sucesso:

```yaml
resources:
  jobs:
    pipeline:
      tasks: [...]

      # Notificação por email
      on_failure:
        email_notifications:
          on_failure:
            - "data-team@company.com"

      on_success:
        email_notifications:
          on_success:
            - "data-lead@company.com"
```

**Gotcha:** Não há webhook direto em Jobs. Use `on_failure` / `on_success` para email.

---

## Templating de Parâmetros

Valores dinâmicos em runtime:

```yaml
parameters:
  - name: env
    default: "dev"
  - name: date
    default: "{{start_date}}"  # Dinâmico

tasks:
  - task_key: extract
    notebook_task:
      notebook_path: ../src/extract.py
      base_parameters:
        env: "{{job.parameters.env}}"
        run_date: "{{job.parameters.date}}"
```

**Variáveis Dinâmicas:**
- `{{start_date}}` — Data de início da run
- `{{end_date}}` — Data de término
- `{{job.parameters.env}}` — Parâmetro nomeado
- `{{job.task_trigger_time}}` — Timestamp trigger

**Em Notebook:**
```python
env = dbutils.widgets.get("env")
date = dbutils.widgets.get("run_date")
```

---

## Permissões — Limitação: Grupo "admins"

**Não é possível modificar permissões do grupo "admins" em Jobs.**

```yaml
resources:
  jobs:
    my_job:
      permissions:
        - level: CAN_VIEW
          group_name: "users"
        - level: CAN_MANAGE_RUN
          group_name: "data_engineers"
        # ❌ Isto falhará:
        # - level: CAN_MANAGE
        #   group_name: "admins"
```

**Gotcha:** Grupo "admins" tem permissão total automaticamente. Não inclua em `permissions`.

---

## Boas Práticas Críticas

### 1. Sempre Retry com Exponential Backoff
```yaml
max_retries: 2
retry_on_timeout: true
timeout_seconds: 3600
```

### 2. Use `depends_on` com `run_if` Explícito
```yaml
depends_on:
  - task_key: previous
run_if: ALL_SUCCESS  # Explícito é melhor
```

### 3. Idempotência Token para Run Manual
```python
idempotency_token = f"etl-{datetime.now().date()}"
```

### 4. Notificações em Alertas Críticos
```yaml
on_failure:
  email_notifications:
    on_failure: ["oncall@company.com"]
```

### 5. Timeout por Task, Não por Job
```yaml
timeout_seconds: 1800  # 30 min por task
```

---

## Matriz: Task Types por Caso de Uso

| Caso de Uso | Task Type | Compute |
|-------------|-----------|---------|
| Notebook exploração | `notebook_task` | Job Cluster |
| Script Python bruto | `spark_python_task` | Job Cluster |
| Pacote ML compilado | `python_wheel_task` | Serverless |
| Query SQL | `sql_task` | SQL Warehouse |
| Transformações dbt | `dbt_task` | Job Cluster |
| Trigger pipeline | `pipeline_task` | SDP (próprio compute) |
| Chamar job externo | `run_job_task` | Nenhum (indireto) |
| Processamento em lote | `for_each_task` | Job Cluster |

---

## Checklist Implementação

- [ ] Retry policy configurada (max_retries: 2)
- [ ] `run_if` conditions explícitas em dependências
- [ ] Scheduling cron validado (quartz format)
- [ ] Idempotency tokens em run manual
- [ ] Alertas email em on_failure
- [ ] Timeouts por task defini
- [ ] Grupo "admins" NUNCA em permissions
- [ ] Parameters validados com `dbutils.widgets.get()`
