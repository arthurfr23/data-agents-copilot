# Monitoramento e Alertas: Tempo Real

Configuração de alertas no Fabric Activator e Databricks. Thresholds por tipo de anomalia. Integração com Teams/Slack.

---

## Arquitetura de Alertas

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Data Sources (Bronze/Silver/Gold)                        │
│         ↓                                                   │
│  System Tables + KQL Queries (Fabric)                     │
│  SQL Queries (Databricks)                                 │
│         ↓                                                   │
│  SQL Alert Tasks (Databricks Jobs) + Activator (Fabric)   │
│         ↓                                                   │
│  Email + Webhook (Teams/Slack)                            │
│         ↓                                                   │
│  Data Engineer → Investigate → Fix                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Databricks: SQL Alert Tasks

### Setup (já referenciado em orchestration-patterns.md)

```yaml
# resources/jobs.yml
resources:
  jobs:
    quality_monitoring:
      name: "Quality Monitoring Hourly"

      tasks:
        # Alert 1: Freshness check
        - task_key: check_freshness
          sql_task:
            alert:
              alert_id: "550e8400-e29b-41d4-a716-446655440001"
              pause_subscriptions: false
            warehouse_id: "abc123"

        # Alert 2: Completeness check
        - task_key: check_completeness
          sql_task:
            alert:
              alert_id: "550e8400-e29b-41d4-a716-446655440002"
            warehouse_id: "abc123"

        # Alert 3: Volume anomaly
        - task_key: check_volume
          sql_task:
            alert:
              alert_id: "550e8400-e29b-41d4-a716-446655440003"
            warehouse_id: "abc123"

      schedule:
        quartz_cron_expression: "0 * * * ?"  # Cada hora
        timezone_id: "UTC"
```

### Exemplos de Alertas SQL

#### Alert A: Freshness (Últimas 24h)

```sql
-- Nome: "Alert: Dados atrasados > 24h"
-- Dispara se MAX(data_evento) < NOW - 24h

SELECT MAX(data_evento) AS last_event_date
FROM silver_vendas
WHERE data_carga >= current_timestamp() - INTERVAL 24 HOUR
HAVING MAX(data_evento) < current_timestamp() - INTERVAL 24 HOUR
```

**Ação:** Investigar fonte, verificar Auto Loader logs.

#### Alert B: Completeness (Nulls > 5%)

```sql
-- Nome: "Alert: Coluna id_cliente com >5% nulos"

SELECT
  SUM(CASE WHEN id_cliente IS NULL THEN 1 ELSE 0 END) AS null_count,
  COUNT(*) AS total_rows,
  ROUND(100.0 * SUM(CASE WHEN id_cliente IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS null_percent
FROM silver_vendas
WHERE data_carga >= current_timestamp() - INTERVAL 24 HOUR
HAVING ROUND(100.0 * SUM(CASE WHEN id_cliente IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) > 5
```

**Ação:** Verificar schema drift, validação em Bronze.

#### Alert C: Volume Anomaly (Drop >30%)

```sql
-- Nome: "Alert: Volume vendas caiu >30%"

WITH daily_counts AS (
  SELECT
    CAST(data_evento AS DATE) AS data,
    COUNT(*) AS vendas_count
  FROM silver_vendas
  WHERE data_evento >= current_date() - 7
  GROUP BY CAST(data_evento AS DATE)
)
SELECT
  (SELECT vendas_count FROM daily_counts WHERE data = current_date()) AS today_count,
  (SELECT AVG(vendas_count) FROM daily_counts WHERE data < current_date()) AS avg_prev,
  ROUND(100.0 * (
    (SELECT vendas_count FROM daily_counts WHERE data = current_date()) -
    (SELECT AVG(vendas_count) FROM daily_counts WHERE data < current_date())
  ) / (SELECT AVG(vendas_count) FROM daily_counts WHERE data < current_date()), 2) AS percent_change
HAVING ROUND(100.0 * (
    (SELECT vendas_count FROM daily_counts WHERE data = current_date()) -
    (SELECT AVG(vendas_count) FROM daily_counts WHERE data < current_date())
  ) / (SELECT AVG(vendas_count) FROM daily_counts WHERE data < current_date()), 2) < -30
```

**Ação:** Verificar fonte, rejeições em Silver, Auto Loader errors.

#### Alert D: Duplicatas

```sql
-- Nome: "Alert: Duplicatas detectadas em vendas"

SELECT COUNT(*) - COUNT(DISTINCT id_venda) AS duplicate_count
FROM silver_vendas
WHERE data_carga >= current_timestamp() - INTERVAL 24 HOUR
HAVING COUNT(*) - COUNT(DISTINCT id_venda) > 0
```

**Ação:** Investigar Auto Loader checkpoint, deduplicação.

#### Alert E: Data Quality (Expect_or_drop)

```sql
-- Nome: "Alert: Registros removidos por validação"

SELECT
  COUNT(*) AS dropped_records,
  ROUND(100.0 * COUNT(*) /
    (SELECT COUNT(*) FROM bronze_vendas WHERE data_carga >= current_timestamp() - INTERVAL 24 HOUR), 2) AS percent_dropped
FROM bronze_vendas
WHERE valor_total <= 0
  OR id_cliente IS NULL
  OR data_carga >= current_timestamp() - INTERVAL 24 HOUR
HAVING COUNT(*) > 0
```

---

## 2. Fabric: Activator (KQL + Real-Time)

### Configurar Activator

```yaml
# Fabric Lakehouse → Activator
# 1. Criar KQL query
# 2. Configurar trigger (time-based ou data change)
# 3. Definir action (Teams, Email, HTTP webhook)
```

### Exemplo: KQL Query para Freshness

```kusto
// Fabricator query: Check freshness in real-time
silver_vendas
| where data_carga >= now(-24h)
| summarize LastEvent = max(data_evento), EventCount = count()
| where LastEvent < now(-24h)
| project Status = "STALE", LastEvent, EventCount
```

### Configurar Trigger e Action

```json
{
  "trigger": {
    "type": "schedule",
    "frequency": "hourly"
  },
  "action": {
    "type": "teams",
    "webhookUrl": "https://outlook.webhook.office.com/webhookb2/...",
    "messageTemplate": {
      "title": "Data Quality Alert",
      "text": "@{LastEvent} - Vendas data not updated in last 24h. Event count: @{EventCount}"
    }
  }
}
```

---

## 3. System Tables (Databricks Audit)

### Monitorar Acessos Anômalos

```sql
-- Ver quem acessou Gold tables
SELECT
  timestamp,
  user_name,
  action,
  resource_id,
  source_ip_address
FROM system.access.audit
WHERE
  object_type = 'TABLE'
  AND database_name = 'gold'
  AND timestamp >= current_timestamp() - INTERVAL 24 HOUR
ORDER BY timestamp DESC;

-- Detectar padrão incomum (ex: bulk export)
SELECT
  user_name,
  COUNT(*) AS access_count,
  COLLECT_SET(DISTINCT resource_id) AS tables_accessed
FROM system.access.audit
WHERE
  action = 'SELECT'
  AND database_name IN ('gold', 'silver')
  AND timestamp >= current_timestamp() - INTERVAL 1 HOUR
GROUP BY user_name
HAVING COUNT(*) > 50  -- Threshold: mais de 50 queries em 1h = suspeito
ORDER BY access_count DESC;
```

---

## Thresholds Recomendados por Tipo

### Freshness (Horas desde última atualização)

| Tabela | Threshold | SLA |
|--------|-----------|-----|
| **silver_vendas** | > 2h | Critical |
| **silver_cliente** | > 24h | Warning |
| **gold_fact_receita** | > 4h | Critical |
| **bronze_*** | > 3h | Warning |

### Completeness (% de nulls)

| Coluna | Threshold | Ação |
|--------|-----------|------|
| **id_cliente (FK)** | > 1% | Alert + expect_or_drop |
| **valor_total (métrica)** | > 2% | Alert + review |
| **data_evento (dimensão)** | > 0.5% | Alert + investigate |
| **email (opcional)** | > 10% | Warning only |

### Volume (% change vs baseline)

| Cenário | Threshold | Ação |
|---------|-----------|------|
| **Volume drop** | < -30% | Critical alert |
| **Volume spike** | > +50% | Warning alert |
| **Zero records** | = 0 | Critical alert |
| **Baseline drift** | ±20% over 7d | Investigate trend |

### Latência (Minutos de delay)

| Etapa | Threshold | SLA |
|-------|-----------|-----|
| **Auto Loader → Bronze** | > 10m | Warning |
| **Bronze → Silver** | > 15m | Warning |
| **Silver → Gold** | > 20m | Critical |
| **Total end-to-end** | > 60m | Critical |

---

## Integração com Teams/Slack

### Webhook Teams

```python
# Python: Enviar alert para Teams
import requests
from datetime import datetime

def send_teams_alert(title, message, severity):
    webhook_url = "https://outlook.webhook.office.com/webhookb2/..."

    color_map = {
        'CRITICAL': 'ff0000',  # Red
        'WARNING': 'ffaa00',   # Orange
        'INFO': '0000ff'       # Blue
    }

    payload = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": title,
        "themeColor": color_map.get(severity, '0000ff'),
        "sections": [{
            "activityTitle": title,
            "activitySubtitle": f"Severity: {severity} | Time: {datetime.now().isoformat()}",
            "facts": [
                {"name": "Table", "value": "silver_vendas"},
                {"name": "Alert", "value": message},
                {"name": "Last Event", "value": "2026-04-09 10:45:00"}
            ]
        }]
    }

    response = requests.post(webhook_url, json=payload)
    return response.status_code == 200
```

### Webhook Slack

```python
# Python: Enviar alert para Slack
import requests

def send_slack_alert(title, message, severity):
    webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

    color_map = {
        'CRITICAL': 'danger',   # Red
        'WARNING': 'warning',   # Orange
        'INFO': 'good'          # Green
    }

    payload = {
        "text": title,
        "attachments": [{
            "fallback": title,
            "color": color_map.get(severity, 'good'),
            "title": title,
            "text": message,
            "fields": [
                {"title": "Severity", "value": severity, "short": True},
                {"title": "Table", "value": "silver_vendas", "short": True}
            ]
        }]
    }

    response = requests.post(webhook_url, json=payload)
    return response.status_code == 200
```

---

## Estrutura de Escalação

```
Alerta Dispara (SQL Alert Task)
         ↓
Email para data-team@company.com
         ↓
Teams/Slack notification (bridge)
         ↓
Data Engineer recebe (< 5 min)
         ↓
Investigação (check logs, run profiling)
         ↓
Root cause (bad data, wrong config, etc)
         ↓
Fix implemented + documented
         ↓
Validation + close alert
```

---

## Checklist de Monitoramento

- [ ] 5+ SQL Alert Tasks configuradas (freshness, completeness, volume, duplicatas, quality)
- [ ] Alertas agendados a cada 1h (ou mais frequente se crítico)
- [ ] Webhooks Teams/Slack testados
- [ ] Thresholds por tipo de anomalia definidos
- [ ] System Tables queries configuradas para audit
- [ ] Dashboard de alerts criado (Databricks SQL)
- [ ] Runbook de investigação documentado
- [ ] Escalação para data owner definida
- [ ] Testes de alerta (simular condição, verificar notificação)
- [ ] Monitoramento de latência end-to-end ativado
