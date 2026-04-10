# KB: Real-Time Intelligence (RTI) e Eventhouse

**Domínio:** Arquitetura Eventhouse, ingestão streaming, KQL, e automação em tempo real.
**Palavras-chave:** Eventhouse, KQL Database, Eventstream, Activator, Time-Series, Materialized Views.

---

## O que é Real-Time Intelligence (RTI)?

RTI combina Eventhouse (KQL Database) + Eventstream + Activator para análise streaming:

| Componente | Função | Exemplo |
|------------|--------|---------|
| **Eventhouse** | KQL Database para armazenar eventos | logs, sensores, clickstream |
| **Eventstream** | Ingestion hub (Kafka, Event Hub) | conecta Event Hub → Eventhouse |
| **Activator** | Alertas automáticos baseados em thresholds | anomalia detectada → email |

**Latência:** <1 segundo (vs. Lakehouse: minutes).

---

## Eventhouse (KQL Database)

Eventhouse é um "data warehouse para streaming" na linguagem KQL (Kusto Query Language):

### Estrutura de Dados
```
Eventhouse (Container)
├── Table_01 (ingestion contínua)
├── Table_02 (batch)
└── MaterializedView_01 (agregação em tempo real)
```

### Criar Tabela Eventhouse
```kusto
// Via REST API ou Fabric UI
// POST /workspaces/{id}/eventhouse/{eventhouse-id}/tables
// Schema automático (auto-detect) ou manual:

{
  "tableName": "user_events",
  "schema": [
    {"columnName": "timestamp", "columnType": "datetime"},
    {"columnName": "user_id", "columnType": "string"},
    {"columnName": "event_type", "columnType": "string"},
    {"columnName": "value", "columnType": "real"}
  ]
}
```

### Metadata (Inspeção)

```kusto
// Listar tabelas
.show tables

// Detalhes de coluna
.show table user_events columns

// Plano de ingestion
.show ingestion csv mapping

// Políticas de retenção
.show retention policy
```

---

## KQL Query Language (vs SQL)

KQL é otimizado para time-series queries (NOT standard SQL):

### Sintaxe KQL

```kusto
// SELECT → aggregation
user_events
| where timestamp > ago(1h)
| summarize count() by event_type, bin(timestamp, 5m)
| order by timestamp desc

// JOIN (pipeline)
user_events
| join kind=left (
    user_master on user_id
) on user_id
| project timestamp, event_type, user_name

// Agregações
user_events
| summarize
    total_events=count(),
    unique_users=dcount(user_id),
    avg_value=avg(value)
    by bin(timestamp, 1h)
```

### Diferenças SQL vs KQL

| Aspecto | SQL | KQL |
|---------|-----|-----|
| **Sintaxe** | SELECT ... FROM | table \| aggregation |
| **JOINs** | INNER/LEFT/FULL | kind=left/inner/semi |
| **Agregações** | GROUP BY | summarize by |
| **Função Tempo** | DATE_TRUNC() | bin(timestamp, 1h) |
| **Performance** | Index-based | Column-based scans |

**Gotcha:** KQL não suporta UPDATE/DELETE — use novo schema + materialized view.

---

## Eventstream (Ingestion Pipeline)

Eventstream é o hub de ingestão:

### Fontes Suportadas

| Fonte | Padrão | Nota |
|-------|--------|------|
| **Kafka** | Topic + Consumer Group | Default em clouds |
| **Event Hub** | Connection string | Azure nativo |
| **Event Grid** | Topic subscription | Serverless |
| **Cosmos DB** | Change Feed | NoSQL events |
| **Custom Source** | HTTP POST | API genérica |

### Exemplo: Event Hub → Eventhouse

```http
POST /workspaces/{workspace-id}/eventstreams
{
  "displayName": "user-events-stream",
  "type": "EventStream",
  "sources": [
    {
      "type": "EventHub",
      "connectionId": "{connection-id}",
      "eventHubName": "user-events",
      "consumerGroup": "$Default"
    }
  ],
  "destinations": [
    {
      "type": "Eventhouse",
      "eventhouseId": "{eventhouse-id}",
      "tableName": "user_events",
      "mappingType": "Json"
    }
  ]
}
```

### Ingestion de Exemplo

```json
// Evento incomingdo (formato JSON)
{
  "timestamp": "2026-04-09T15:30:45Z",
  "user_id": "user_123",
  "event_type": "page_view",
  "value": 42.5
}
```

---

## Activator (Alertas Automáticos)

Activator monitora thresholds e dispara ações (email, webhook):

### Configurar Trigger

```http
POST /workspaces/{workspace-id}/activator/{activator-id}/triggers
{
  "displayName": "High Error Rate Alert",
  "query": "KQL: user_events | where event_type == 'error' | count",
  "condition": "count > 100",
  "timeWindow": "5m",
  "action": {
    "type": "Email",
    "recipients": ["ops@company.com"],
    "subject": "Error spike detected",
    "body": "Count: {result}"
  }
}
```

### Padrões de Triggers

| Condição | Exemplo | Resposta |
|----------|---------|----------|
| **Threshold excedido** | `count > 1000` | Email SLA |
| **Anomalia detectada** | `stdev(value) > 3*mean` | Slack notification |
| **Sem dados (dead source)** | `count == 0 for 10m` | PagerDuty alert |
| **Degradação** | `latency > 5s` | Dashboard highlight |

---

## Ingestão com kusto_ingest_inline_into_table

Para ingestão Spark → Eventhouse (via SDK):

```python
# Python SDK (pyfabricops style)
from kusto_client import KustoConnectionStringBuilder, KustoClient
from kusto_client.ingest import KustoIngestClient, IngestionProperties, BlobDescriptor

# Configurar conexão
kcsb = KustoConnectionStringBuilder.with_aad_application_key_authentication(
    kusto_cluster="https://{cluster}.kusto.windows.net",
    aad_app_id="{app_id}",
    app_key="{app_key}",
    authority_id="{tenant_id}"
)

client = KustoIngestClient(kcsb)

# Ingestão em lote (via blob)
ingestion_props = IngestionProperties(
    database="{database}",
    table="{table_name}",
    format=DataFormat.CSV,
    ingestion_mapping_reference="csv_mapping"
)

blob_descriptor = BlobDescriptor(blob_path, size=blob_size)
client.ingest_from_blob(blob_descriptor, ingestion_props)
```

**Alternativa REST (simples):**
```http
POST https://{cluster}.kusto.windows.net/v1/rest/ingest
{
  "db": "database_name",
  "csl": ".ingest inline into user_events <| user_id,timestamp,event_type\nuser_123,2026-04-09T15:30Z,click"
}
```

---

## Retention Policies (Dados Históricos)

```kusto
// Configurar retenção: 30 dias de hot data, 365 dias total
.alter-merge table user_events policy retention
  softdelete = 30d, recoverability = 365d

// Retenção zero (temporal)
.alter table user_events policy retention
  softdelete = 0d, recoverability = 0d
```

| Tier | Duração | SLA | Custo |
|------|---------|-----|-------|
| **Hot** | 30-90 dias | <1s | $normal |
| **Warm** | 90-365 dias | ~10s | $reduced |
| **Cold** | 365+ dias | ~1m | $minimal |

---

## Materialized Views (Agregações Contínuas)

Views que atualizam em tempo real (sem latência):

```kusto
// Criar MV: agregação por hora
.create materialized-view hourly_stats
  on table user_events
{
  user_events
  | summarize
      event_count=count(),
      unique_users=dcount(user_id),
      avg_value=avg(value)
      by bin(timestamp, 1h), event_type
}

// Querying MV (instantâneo)
hourly_stats
| where timestamp > ago(24h)
| order by timestamp desc
```

**Custo:** Ligeiramente superior a tabelas normais (recompute contínuo).

---

## .show Commands (Troubleshooting)

```kusto
// Verificar status de ingestion
.show ingestion failures
| where table == "user_events"
| order by FailedOn desc
| limit 10

// Tamanho de tabela
.show table user_events extents
| summarize TotalSize = sum(ExtentSize)

// Diagnóstico de performance
.show table user_events cslschema
| project ColumnName, ColumnType

// Estatísticas de retenção
.show table user_events retention policy
```

---

## Hot/Warm/Cold Tiering

Eventhouse suporta auto-tiering baseado em age:

```kusto
// Política de tiering automático
.alter table user_events policy hot_window
  effective_hot_window = 30d

// Move automaticamente:
// 0-30d: Hot (full index)
// 30-90d: Warm (partial index)
// 90+d: Cold (archive, slow query)
```

| Tier | Latência | Custo | Auto-transition |
|------|----------|-------|-----------------|
| Hot | <1s | $$$$ | T+0d |
| Warm | ~10s | $$ | T+30d |
| Cold | ~60s | $ | T+90d |

---

## Decision Matrix: Lakehouse vs Eventhouse

```
Use Lakehouse quando:
  → Dados batch (diários, horários)
  → Schema estável, transformações complexas
  → BI/Reports com Direct Lake
  → Volume: 100GB-10TB

Use Eventhouse quando:
  → Streaming contínuo (eventos/logs)
  → Real-time dashboards (<1s latência)
  → Alertas automáticos (Activator)
  → Volume: 1M-10M eventos/dia
  → TTL curto (<90 dias)
```

---

## Checklist RTI Implementation

- [ ] Eventhouse criado com schema pré-definido
- [ ] Eventstream conectado (Kafka/Event Hub/Custom)
- [ ] Ingestão validada (0 failures por 24h)
- [ ] Materialized views para agregações críticas
- [ ] Retention policies configuradas (hot=30d, cold=365d)
- [ ] Activator triggers testados (email/webhook)
- [ ] Queries KQL otimizadas (use `.show performance_stats`)
- [ ] Monitoramento: `.show ingestion failures` em alert
- [ ] Documentação: KQL query library versionada no Git
