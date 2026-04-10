# SLA Contracts: Contrato de Qualidade de Dados

Template de contrato SLA per tabela. Dimensões de qualidade, owner, alertas, escalação.

---

## Conceito: SLA vs Expectation

| Aspecto | SLA | Expectation |
|--------|-----|-----------|
| **Escopo** | Contrato formal por tabela | Validação em código |
| **Público** | Data owner, analytics team | Data engineers |
| **Frequência** | Monitorado continuamente | Executado a cada pipeline run |
| **Violação** | Incident, post-mortem | Pipeline falha, refaz |
| **Documento** | Tabela SQL, contrato | Decorator @dp.expect_or_fail |

---

## Template de SLA Contract

### Tabela: silver_vendas

```yaml
# SLA Contrato
contract_id: "SLA-SLV-VENDAS-001"
table_name: "catalog.silver.vendas"
catalog: "prod_catalog"
schema: "silver"

# Proprietário
data_owner: "Data Product Manager - Sales"
data_owner_email: "sales-dpm@company.com"
backup_owner: "Senior Data Engineer"
backup_owner_email: "data-eng-lead@company.com"

# Dimensões de Qualidade
sla:
  freshness:
    max_hours_since_update: 4  # Máximo 4h sem atualização
    definition: "MAX(data_carga) >= NOW() - INTERVAL 4 HOUR"
    severity: "CRITICAL"

  completeness:
    min_nonnull_percent: 95  # Mínimo 95% não-nulo
    critical_columns: ["id_cliente", "valor_total", "data_evento"]
    definition: "COUNT(id_cliente) / COUNT(*) >= 0.95"
    severity: "CRITICAL"

  availability:
    min_uptime_percent: 99.5  # SLA 99.5% de uptime
    maintenance_window: "2-4 AM UTC, Sundays"
    definition: "Rolling 7-day uptime >= 99.5%"
    severity: "HIGH"

  uniqueness:
    no_duplicates: true
    unique_keys: ["id_venda"]
    definition: "COUNT(*) = COUNT(DISTINCT id_venda)"
    severity: "CRITICAL"

  validity:
    valid_statuses: ["ATIVO", "CANCELADO", "RETORNADO"]
    valid_valor_range: [0, 1000000]  # 0 até 1M
    definition: "status IN ('ATIVO', 'CANCELADO', 'RETORNADO') AND valor_total BETWEEN 0 AND 1000000"
    severity: "CRITICAL"

# Monitoramento
monitoring:
  frequency: "Hourly"
  check_schedule: "0 * * * ?"  # Cron: cada hora
  dashboard_url: "https://databricks.../dashboard/sla-silver-vendas"

# Alertas
alerts:
  - dimension: "freshness"
    threshold: "max_hours >= 4"
    channels: ["teams", "pagerduty"]
    recipients: ["sales-dpm@company.com"]
    escalation_after_minutes: 30

  - dimension: "completeness"
    threshold: "nonnull_pct < 95"
    channels: ["email", "slack"]
    recipients: ["data-eng-lead@company.com"]
    escalation_after_minutes: 60

  - dimension: "availability"
    threshold: "uptime_7d < 99.5%"
    channels: ["pagerduty"]
    recipients: ["data-eng-lead@company.com"]
    escalation_after_minutes: 15

# Refresh Schedule
refresh:
  frequency: "Every 2 hours"
  start_time: "02:00 UTC"
  expected_duration_minutes: 30
  retry_policy: "3 attempts, 10 minute backoff"
  failure_notification: "Immediate to data_owner"

# SLO Targets
targets:
  - metric: "Freshness (hours since update)"
    target: "< 4 hours"
    measurement_period: "Daily"

  - metric: "Completeness (% non-null in critical columns)"
    target: ">= 95%"
    measurement_period: "Daily"

  - metric: "No unresolved schema drift"
    target: "Zero"
    measurement_period: "Weekly"

# Violação e Escalonamento
escalation:
  level_1:
    trigger: "SLA violated by < 50%"
    response_time: "15 minutes"
    owner: "on-call data engineer"
    action: "Investigate, post update in #data-incidents"

  level_2:
    trigger: "SLA violated by 50-100%"
    response_time: "5 minutes"
    owner: "data-eng-lead"
    action: "Immediate fix or rollback"
    notify: ["sales-dpm@company.com"]

  level_3:
    trigger: "SLA violated > 2 hours"
    response_time: "Immediate"
    owner: "data-eng-director"
    action: "Page on-call, assess impact, rollback/fix"
    notify: ["analytics-team@company.com", slack channel]

# Post-Mortem
postmortem:
  required_if: "SLA violated > 1 hour OR data quality impact > 1000 rows"
  timeline: "Within 24 hours of resolution"
  attendees: ["data_owner", "data engineer", "impact affected teams"]
  documentation: "Root cause, prevention, action items"
```

---

## Tabela de SLA Contracts (Catalog)

```sql
-- Manter registro de todos os contratos SLA
CREATE TABLE IF NOT EXISTS catalog.quality.sla_contracts (
  contract_id STRING,
  table_name STRING,
  catalog STRING,
  schema STRING,

  -- Proprietário
  data_owner STRING,
  data_owner_email STRING,
  backup_owner STRING,

  -- Dimensões (JSON para flexibilidade)
  sla_freshness_hours INT,  -- Max hours sem update
  sla_completeness_pct DOUBLE,  -- Min % non-null
  sla_availability_pct DOUBLE,  -- Min uptime %
  sla_uniqueness_required BOOLEAN,
  sla_unique_keys STRING,  -- Comma-separated
  sla_valid_values STRING,  -- JSON com domínios

  -- Monitoramento
  monitoring_frequency STRING,  -- Hourly, Daily, etc
  dashboard_url STRING,
  alert_channels STRING,  -- JSON array: teams, pagerduty, slack

  -- Escalação
  escalation_level_1_minutes INT,  -- Response time
  escalation_level_2_minutes INT,
  escalation_level_3_minutes INT,

  -- Refresh
  refresh_frequency STRING,
  refresh_start_time TIME,
  refresh_expected_duration_minutes INT,

  -- Audit
  created_date DATE,
  created_by STRING,
  last_updated_date DATE,
  last_updated_by STRING,
  active BOOLEAN
);

-- Exemplo: Inserir SLA para silver_vendas
INSERT INTO catalog.quality.sla_contracts VALUES (
  'SLA-SLV-VENDAS-001',
  'catalog.silver.vendas',
  'prod_catalog',
  'silver',
  'Sales DPM',
  'sales-dpm@company.com',
  'Data Eng Lead',
  4,  -- Máx 4h sem update
  95,  -- Mín 95% completo
  99.5,  -- 99.5% uptime
  true,  -- Unicidade obrigatória
  'id_venda',
  '{"status": ["ATIVO", "CANCELADO"], "valor": [0, 1000000]}',
  'Hourly',
  'https://databricks.../dashboard/...',
  '["teams", "pagerduty"]',
  30,  -- Level 1: 30 min
  5,   -- Level 2: 5 min
  15,  -- Level 3: immediate (15s)
  'Every 2 hours',
  TIME '02:00:00',
  30,
  CURRENT_DATE(),
  'admin@company.com',
  CURRENT_DATE(),
  'admin@company.com',
  true
);
```

---

## Monitoramento Contínuo de SLA

### Verificação Horária

```sql
-- Query executada a cada hora (SQL Alert Task)
WITH sla_check AS (
  SELECT
    'silver_vendas' AS table_name,

    -- Freshness
    MAX(data_carga) AS last_update,
    CASE
      WHEN DATEDIFF(CURRENT_TIMESTAMP(), MAX(data_carga)) > 4 THEN 'VIOLATED'
      ELSE 'OK'
    END AS freshness_status,

    -- Completeness
    ROUND(100.0 * SUM(CASE WHEN id_cliente IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS completeness_pct,
    CASE
      WHEN 100.0 * SUM(CASE WHEN id_cliente IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*) < 95 THEN 'VIOLATED'
      ELSE 'OK'
    END AS completeness_status,

    -- Uniqueness
    COUNT(*) AS total_rows,
    COUNT(DISTINCT id_venda) AS distinct_rows,
    CASE
      WHEN COUNT(*) = COUNT(DISTINCT id_venda) THEN 'OK'
      ELSE 'VIOLATED'
    END AS uniqueness_status,

    -- Validity
    SUM(CASE WHEN status NOT IN ('ATIVO', 'CANCELADO', 'RETORNADO') THEN 1 ELSE 0 END) AS invalid_status_count,
    CASE
      WHEN SUM(CASE WHEN status NOT IN ('ATIVO', 'CANCELADO', 'RETORNADO') THEN 1 ELSE 0 END) > 0 THEN 'VIOLATED'
      ELSE 'OK'
    END AS validity_status,

    CURRENT_TIMESTAMP() AS check_timestamp
  FROM silver_vendas
)
SELECT * FROM sla_check
WHERE freshness_status = 'VIOLATED'
   OR completeness_status = 'VIOLATED'
   OR uniqueness_status = 'VIOLATED'
   OR validity_status = 'VIOLATED';
```

### Log de Violações

```sql
-- Armazenar histórico de violações
CREATE TABLE IF NOT EXISTS catalog.quality.sla_violations (
  violation_id STRING,
  contract_id STRING,
  table_name STRING,
  dimension STRING,  -- freshness, completeness, etc
  sla_threshold STRING,  -- "< 4 hours", ">= 95%"
  actual_value STRING,  -- "5.5 hours", "92.3%"
  violation_severity STRING,  -- CRITICAL, HIGH, MEDIUM
  violation_start TIMESTAMP,
  violation_resolved TIMESTAMP,
  resolution_action STRING,
  created_by STRING
);

-- Inserir violação
INSERT INTO catalog.quality.sla_violations
VALUES (
  CONCAT('VIO-', CURRENT_TIMESTAMP_MS()),
  'SLA-SLV-VENDAS-001',
  'silver_vendas',
  'FRESHNESS',
  'MAX(data_carga) >= NOW() - 4h',
  'Last update 5.2 hours ago',
  'CRITICAL',
  CURRENT_TIMESTAMP(),
  NULL,
  NULL,
  'monitoring-system'
);
```

### Dashboard de SLA

```sql
-- View para dashboard: SLA Status
CREATE VIEW IF NOT EXISTS catalog.quality.sla_status AS
SELECT
  c.contract_id,
  c.table_name,
  c.data_owner,

  -- Freshness
  (SELECT MAX(data_carga) FROM silver_vendas) AS last_update,
  DATEDIFF(CURRENT_TIMESTAMP(), (SELECT MAX(data_carga) FROM silver_vendas)) AS hours_since_update,
  c.sla_freshness_hours,
  CASE
    WHEN DATEDIFF(CURRENT_TIMESTAMP(), (SELECT MAX(data_carga) FROM silver_vendas)) <= c.sla_freshness_hours
    THEN 'PASS' ELSE 'FAIL'
  END AS freshness_status,

  -- Overall Status
  CASE
    WHEN DATEDIFF(CURRENT_TIMESTAMP(), (SELECT MAX(data_carga) FROM silver_vendas)) > c.sla_freshness_hours
    THEN 'VIOLATED' ELSE 'OK'
  END AS overall_sla_status,

  CURRENT_TIMESTAMP() AS check_time
FROM catalog.quality.sla_contracts c;
```

---

## Escalação Automática

### Task de Escalação (DABs)

```yaml
resources:
  jobs:
    sla_escalation:
      name: "SLA Escalation Hourly"

      tasks:
        - task_key: check_sla
          sql_task:
            alert:
              alert_id: "sla-check-alert"
            warehouse_id: "abc123"

        - task_key: escalate_if_violated
          depends_on:
            - task_key: check_sla
          run_if: "AT_LEAST_ONE_FAILED"  # Só executa se SLA falhou
          notebook_task:
            notebook_path: ../src/escalate_sla_violation
            base_parameters:
              escalation_level: "1"
```

### Python: Lógica de Escalação

```python
# Escalação automática baseada em duração da violação
from datetime import datetime, timedelta
import requests

def escalate_sla_violation(table_name, violation_duration_minutes):
    # Ler SLA contract
    contract = spark.read.table("catalog.quality.sla_contracts") \
        .filter(f"table_name = '{table_name}'").collect()[0]

    # Determinar nível de escalação
    if violation_duration_minutes <= contract['escalation_level_1_minutes']:
        level = 1
        owner = "on-call-data-engineer"
        urgency = "medium"
    elif violation_duration_minutes <= contract['escalation_level_2_minutes']:
        level = 2
        owner = contract['data_owner_email']
        urgency = "high"
    else:
        level = 3
        owner = "data-eng-director"
        urgency = "critical"

    # Enviar notificação
    send_escalation_alert(
        level=level,
        owner=owner,
        urgency=urgency,
        table=table_name,
        duration=violation_duration_minutes
    )

    # Log em metadados
    spark.sql(f"""
        INSERT INTO catalog.quality.sla_violations
        VALUES (
            CONCAT('VIO-', CURRENT_TIMESTAMP_MS()),
            '{contract['contract_id']}',
            '{table_name}',
            'ESCALATION_LEVEL_{level}',
            'Violation duration > {violation_duration_minutes} min',
            '{urgency}',
            CURRENT_TIMESTAMP(),
            NULL,
            'Escalation triggered',
            'system'
        )
    """)

def send_escalation_alert(level, owner, urgency, table, duration):
    # Webhook para Teams/PagerDuty
    webhook = "https://outlook.webhook.office.com/webhookb2/..."
    payload = {
        "summary": f"SLA ESCALATION Level {level}: {table}",
        "themeColor": "ff0000" if level == 3 else "ffaa00",
        "facts": [
            {"name": "Table", "value": table},
            {"name": "Escalation Level", "value": str(level)},
            {"name": "Violation Duration", "value": f"{duration} minutes"},
            {"name": "Urgency", "value": urgency}
        ]
    }
    requests.post(webhook, json=payload)
```

---

## Checklist de SLA Contracts

- [ ] Template YAML criado e documentado
- [ ] Tabela `catalog.quality.sla_contracts` criar e populated
- [ ] SLAs definidos para todas as Gold tables
- [ ] SLAs definidos para críticas Silver tables
- [ ] Monitoramento horário configurado (SQL Alert Task)
- [ ] Tabela `catalog.quality.sla_violations` criada
- [ ] Dashboard de SLA status criado
- [ ] Escalação automática implementada (3 níveis)
- [ ] Notificações (Teams/PagerDuty/Email) testadas
- [ ] Runbook de remediação documentado
- [ ] Post-mortem process defined e documentado
