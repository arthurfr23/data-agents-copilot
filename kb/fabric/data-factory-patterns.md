# KB: Data Factory Padrões e Orquestração

**Domínio:** Pipelines de dados, Dataflow Gen2, scheduling, monitoramento e error handling.
**Palavras-chave:** Data Pipeline, Copy Activity, Dataflow Gen2, Scheduling, LRO Polling.

---

## O que é Data Factory no Fabric?

Data Factory é o orquestrador de pipelines (ETL/ELT):

| Componente | Função | Exemplo |
|-----------|--------|---------|
| **Pipeline** | Fluxo de atividades sequenciais/paralelas | Copy → Transform → Load |
| **Copy Activity** | Move dados entre fontes/destinos | SQL → Lakehouse |
| **Dataflow Gen2** | Transformação visual Power Query | Clean + join |
| **Notebook Activity** | Executa Spark/Python | Custom Spark ETL |
| **Scheduling** | Trigger recorrente (cron) | Daily 2 AM UTC |

**Latência:** 5-30 min (batch); use RTI para real-time.

---

## Data Pipeline (CRUD via REST API)

### Criar Pipeline

```http
POST /workspaces/{workspace-id}/dataPipelines
Content-Type: application/json

{
  "displayName": "DailyETL",
  "description": "Daily ingestion from CRM to Gold",
  "definition": {
    "activities": [
      {
        "name": "CopyCRM",
        "type": "Copy",
        "typeProperties": {
          "source": {
            "type": "SqlServerSource",
            "query": "SELECT * FROM Customer WHERE updated_at > @lastRunTime"
          },
          "sink": {
            "type": "LakehouseTableSink",
            "lakehouseId": "{lakehouse-id}",
            "tableName": "customer_bronze"
          }
        },
        "retryPolicy": {
          "count": 3,
          "intervalInSeconds": 30
        }
      }
    ]
  }
}
```

### Listar Pipelines

```http
GET /workspaces/{workspace-id}/dataPipelines
```

**Response:**
```json
{
  "value": [
    {
      "id": "pipeline-123",
      "displayName": "DailyETL",
      "lastUpdatedTime": "2026-04-09T12:00:00Z"
    }
  ]
}
```

### Obter Definição de Pipeline

```http
GET /workspaces/{workspace-id}/dataPipelines/{pipeline-id}/getDefinition
```

**Response:**
```json
{
  "definition": "base64-encoded-json"
}
```

### Atualizar Pipeline

```http
PATCH /workspaces/{workspace-id}/dataPipelines/{pipeline-id}/updateDefinition
Content-Type: application/json

{
  "definition": "base64-encoded-json-updated"
}
```

### Deletar Pipeline

```http
DELETE /workspaces/{workspace-id}/dataPipelines/{pipeline-id}
```

---

## Copy Activity (Padrões)

### Fonte: SQL Database

```json
{
  "source": {
    "type": "SqlServerSource",
    "sqlReaderQuery": "SELECT * FROM Sales WHERE date >= @{pipeline().parameters.startDate}",
    "queryTimeout": 300
  }
}
```

### Destino: Lakehouse (Bronze)

```json
{
  "sink": {
    "type": "LakehouseTableSink",
    "lakehouseId": "abc-123",
    "tableProperties": {
      "name": "sales_bronze",
      "mode": "overwrite"
    }
  }
}
```

### Retry e Error Handling

```json
{
  "retryPolicy": {
    "count": 3,
    "intervalInSeconds": 30,
    "type": "ExponentialBackoff"
  },
  "continueOnError": true,
  "errorPolicy": {
    "type": "SkipFailedRows",
    "failurePercentage": 5
  }
}
```

| Propriedade | Efeito | Uso |
|------------|--------|-----|
| **count** | Número de retentativas | 1-5 típico |
| **intervalInSeconds** | Espera entre tentativas | 30-300 |
| **type** | Linear vs Exponential | ExponentialBackoff para APIs |
| **continueOnError** | Não falhe o pipeline | true para tolerância |

---

## Dataflow Gen2 vs Gen1

| Aspecto | Gen1 | Gen2 |
|--------|------|------|
| **Engine** | Power Query (cloud) | Apache Spark |
| **Performance** | Pequeno volume (<10GB) | Grande volume (+10GB) |
| **Paralelismo** | 1 core | Multi-core (Spark clusters) |
| **Reload** | Manual | Schedule automático |
| **Sink** | Lakehouse, SQL, CSV | Lakehouse (preferido) |
| **Recomendação** | UI visual (simples) | Código Spark (complexo) |

### Dataflow Gen2 (Recomendado)

```python
# Spark-based transformation
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp

spark = SparkSession.builder.appName("DailyTransform").getOrCreate()

# Ler de Bronze
df_raw = spark.read.table("customer_bronze")

# Transformar
df_clean = df_raw \
  .filter(col("customer_id").isNotNull()) \
  .withColumn("updated_at", to_timestamp("updated_at", "yyyy-MM-dd")) \
  .dropDuplicates(["customer_id"])

# Escrever em Silver
df_clean.write.format("delta").mode("overwrite") \
  .option("path", "abfss://.../Silver/CRM/customer/") \
  .saveAsTable("customer_silver")
```

### Scheduling Dataflow

```http
POST /workspaces/{workspace-id}/dataflows/{dataflow-id}/refreshSchedules
{
  "value": [
    {
      "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "times": ["02:00"]
    }
  ]
}
```

---

## Scheduling com Cron (Pipelines)

### Trigger: Schedule Recorrente

```http
POST /workspaces/{workspace-id}/dataPipelines/{pipeline-id}/triggers
{
  "name": "DailyRunTrigger",
  "type": "ScheduleTrigger",
  "typeProperties": {
    "recurrence": {
      "frequency": "Day",
      "interval": 1,
      "startTime": "2026-04-10T02:00:00Z",
      "timeZone": "UTC",
      "schedule": {
        "minutes": [0],
        "hours": [2]
      }
    }
  }
}
```

### Cron Patterns (Azure Data Factory Format)

```
Dailey at 2 AM: 0 0 2 * * *
Every 6 hours: 0 0 */6 * * *
Weekdays at 9 AM: 0 0 9 * * 1-5
First day do mês: 0 0 0 1 * *
```

**Nota:** Fabric usa expressões recurrence JSON (não cron direto), traduzir:

| Frequência | Interval | Result |
|-----------|----------|--------|
| Day | 1 | Diário |
| Day | 7 | Semanal |
| Hour | 6 | A cada 6 horas |
| Minute | 30 | A cada 30 min |

---

## Monitoramento via REST API

### Listar Execuções (Job Instances)

```http
GET /workspaces/{workspace-id}/dataPipelines/{pipeline-id}/runs
```

**Response:**
```json
{
  "value": [
    {
      "id": "run-456",
      "startTime": "2026-04-09T02:00:00Z",
      "endTime": "2026-04-09T02:15:00Z",
      "status": "Succeeded"
    }
  ]
}
```

### Detalhes de uma Run

```http
GET /workspaces/{workspace-id}/dataPipelines/{pipeline-id}/runs/{run-id}
```

**Response:**
```json
{
  "id": "run-456",
  "status": "Succeeded",
  "activities": [
    {
      "name": "CopyCRM",
      "status": "Succeeded",
      "output": {
        "rowsCopied": 15000,
        "rowsSkipped": 50,
        "duration": 120000
      }
    }
  ]
}
```

### Monitorar Failures

```python
# Python wrapper pattern
def get_failed_runs(workspace_id, pipeline_id):
    runs = api_request(f"/workspaces/{workspace_id}/dataPipelines/{pipeline_id}/runs")
    failed = [r for r in runs if r['status'] != 'Succeeded']
    return failed

# Log failures
for run in get_failed_runs(workspace_id, pipeline_id):
    print(f"Run {run['id']} failed at {run['endTime']}")
    # Trigger alerting / retry
```

---

## Parameterização de Pipelines

### Definir Parâmetros

```json
{
  "parameters": [
    {
      "name": "startDate",
      "type": "string",
      "defaultValue": "2026-01-01"
    },
    {
      "name": "lakehouseId",
      "type": "string",
      "defaultValue": "default-lakehouse"
    }
  ],
  "activities": [
    {
      "name": "CopyActivity",
      "typeProperties": {
        "source": {
          "sqlReaderQuery": "SELECT * FROM Sales WHERE date >= '@{pipeline().parameters.startDate}'"
        }
      }
    }
  ]
}
```

### Passar Parâmetros na Execução

```http
POST /workspaces/{workspace-id}/dataPipelines/{pipeline-id}/runs
{
  "parameters": {
    "startDate": "2026-04-01",
    "lakehouseId": "analytics-lakehouse"
  }
}
```

---

## Error Handling e Retry

### Configuração Global (Pipeline)

```json
{
  "policy": {
    "timeout": "01:00:00",  // 1 hour timeout
    "retry": 3,             // 3 retries
    "retryIntervalInSeconds": 60
  }
}
```

### Por Activity

```json
{
  "activities": [
    {
      "name": "CriticalCopy",
      "retryPolicy": {
        "count": 5,
        "intervalInSeconds": 120
      },
      "onFailure": [
        {
          "action": "SkipActivityOnFailure"
        }
      ]
    }
  ]
}
```

| Action | Efeito | Quando usar |
|--------|--------|-----------|
| SkipActivityOnFailure | Continua pipeline | Atividades não-críticas |
| StopActivityOnFailure | Falha todo pipeline | Dados críticos |
| Retry | Reexecuta N vezes | API flaky |

---

## Decision Matrix: Copy vs Notebook vs Dataflow

```
Use Copy Activity quando:
  → Mover dados "as-is" (sem transformação)
  → Volumoso (100GB+)
  → Entre sistemas estruturados (SQL→Lakehouse)

Use Dataflow Gen2 quando:
  → Transformações Power Query/Spark
  → Volume moderado (1-50GB)
  → Reutilizar transformações entre pipelines

Use Notebook Activity quando:
  → Lógica customizada complexa
  → Python/R machine learning
  → Debug interativo necessário
```

---

## Checklist Data Factory

- [ ] Pipelines criadas com retry/timeout
- [ ] Trigger schedule configurada (cron/recurrence)
- [ ] Parameterização para dev/test/prod
- [ ] Error handling definido (skip vs stop)
- [ ] Monitoramento: `.show job_instances` > 24h
- [ ] Dataflow Gen2 para transformações (não Gen1)
- [ ] Logging integrado (Lakehouse audit table)
- [ ] Alerting: onfailure → email/webhook
- [ ] SLA documentada: tempo esperado + threshold
