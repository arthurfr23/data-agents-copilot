# Drift Detection: Schema e Data Drift

Detecção automática de mudanças de schema e distribuição de dados. Triggers e protocolos de resposta.

---

## Tipos de Drift

### Schema Drift
**Definição:** Mudanças estruturais no schema (colunas adicionadas, removidas, tipos alterados).

| Tipo | Exemplo | Detecção |
|------|---------|----------|
| **Column Addition** | Nova coluna `promo_code` aparece | Schema comparison diff |
| **Column Removal** | Coluna `legacy_id` desaparece | Schema comparison diff |
| **Type Change** | `valor` STRING → DECIMAL | Type mismatch error |
| **Nullable Change** | `id_cliente` NOT NULL → nullable | Type mismatch error |

### Data Drift
**Definição:** Mudanças estatísticas em dados válidos (distribuição muda, valores anômalos aumentam).

| Tipo | Exemplo | Detecção |
|------|---------|----------|
| **Distribution Shift** | Média de `valor_total` sobe 40% | Percentile comparison |
| **New Values** | Categoria `BLOQUEADO` nunca vista antes | Cardinality check |
| **Null Increase** | Nulls em `email` sobem de 1% para 8% | Null % threshold |
| **Outlier Spike** | Min/max de `valor_total` expandem | Min/max comparison |

---

## Schema Drift: Detecção Automática

### SDP Auto-Evolution

Spark Declarative Pipelines detecta mudanças de schema automaticamente:

```python
# Python SDP com mergeSchema
from pyspark import pipelines as dp

@dp.table(name="bronze_vendas")
def bronze_vendas():
    return spark.readStream.format("cloudFiles") \
        .option("cloudFiles.format", "json") \
        .option("cloudFiles.schemaInferenceMode", "addNewColumns") \
        .option("mergeSchema", "true")  # Auto-evolve schema
        .load("/Volumes/raw/vendas/")
```

**Comportamento:** Novas colunas são adicionadas automaticamente, sem falha de pipeline.

### Schema Comparison Manual

```sql
-- Comparar schema entre execuções
-- Armazenar snapshots de schema e detectar diferenças

-- Tabela de metadados de schema
CREATE TABLE IF NOT EXISTS catalog.quality.schema_history (
  schema_id STRING,
  table_name STRING,
  column_name STRING,
  column_type STRING,
  nullable BOOLEAN,
  ordinal_position INT,
  snapshot_date DATE,
  is_new BOOLEAN,
  is_deleted BOOLEAN
);

-- Snapshot atual
INSERT INTO catalog.quality.schema_history
SELECT
  CONCAT(table_name, '_', current_date()),
  table_name,
  column_name,
  data_type,
  is_nullable,
  ordinal_position,
  current_date(),
  FALSE,
  FALSE
FROM information_schema.columns
WHERE table_catalog = 'main' AND table_schema = 'silver'
ORDER BY table_name, ordinal_position;

-- Detectar novas colunas
SELECT
  current_columns.column_name,
  current_columns.data_type,
  current_columns.ordinal_position,
  'NEW COLUMN' AS change_type
FROM information_schema.columns current_columns
LEFT JOIN catalog.quality.schema_history history
  ON current_columns.column_name = history.column_name
  AND current_columns.table_name = history.table_name
WHERE history.column_name IS NULL
  AND current_columns.table_name = 'silver_vendas';

-- Detectar removidas
SELECT
  history.column_name,
  'DELETED COLUMN' AS change_type
FROM catalog.quality.schema_history history
LEFT JOIN information_schema.columns current_columns
  ON history.column_name = current_columns.column_name
  AND history.table_name = current_columns.table_name
WHERE current_columns.column_name IS NULL
  AND history.table_name = 'silver_vendas'
  AND history.snapshot_date = current_date() - 1;
```

---

## Data Drift: Detecção Estatística

### Protocolo de Profiling Comparativo

```sql
-- Comparar perfil de hoje vs semana passada
WITH today_profile AS (
  SELECT
    'TODAY' AS period,
    COUNT(*) AS row_count,
    COUNT(DISTINCT id_cliente) AS unique_clients,
    MIN(valor_total) AS min_valor,
    MAX(valor_total) AS max_valor,
    ROUND(AVG(valor_total), 2) AS avg_valor,
    ROUND(STDDEV(valor_total), 2) AS stddev_valor,
    ROUND(100.0 * SUM(CASE WHEN id_cliente IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS null_pct,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY valor_total), 2) AS median_valor
  FROM silver_vendas
  WHERE data_evento >= current_date()
),
week_ago_profile AS (
  SELECT
    'WEEK_AGO' AS period,
    COUNT(*) AS row_count,
    COUNT(DISTINCT id_cliente) AS unique_clients,
    MIN(valor_total) AS min_valor,
    MAX(valor_total) AS max_valor,
    ROUND(AVG(valor_total), 2) AS avg_valor,
    ROUND(STDDEV(valor_total), 2) AS stddev_valor,
    ROUND(100.0 * SUM(CASE WHEN id_cliente IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS null_pct,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY valor_total), 2) AS median_valor
  FROM silver_vendas
  WHERE data_evento >= current_date() - 7 AND data_evento < current_date() - 6
)
SELECT
  t.period AS today_period,
  t.row_count AS today_rows,
  w.row_count AS week_ago_rows,
  ROUND(100.0 * (t.row_count - w.row_count) / w.row_count, 2) AS volume_change_pct,
  ROUND(100.0 * (t.avg_valor - w.avg_valor) / w.avg_valor, 2) AS avg_valor_change_pct,
  CASE
    WHEN ABS(ROUND(100.0 * (t.avg_valor - w.avg_valor) / w.avg_valor, 2)) > 20 THEN 'DATA DRIFT: Média alterou >20%'
    WHEN ABS(ROUND(100.0 * (t.row_count - w.row_count) / w.row_count, 2)) > 30 THEN 'DATA DRIFT: Volume alterou >30%'
    WHEN ABS(t.null_pct - w.null_pct) > 5 THEN 'DATA DRIFT: Nulls alteraram >5%'
    WHEN t.max_valor > w.max_valor * 1.5 THEN 'DATA DRIFT: Outlier novo detectado'
    ELSE 'OK'
  END AS drift_status
FROM today_profile t, week_ago_profile w;
```

### Thresholds de Data Drift

| Métrica | Threshold | Ação |
|---------|-----------|------|
| **Média (Avg)** | > 20% de mudança | Alert + investigate |
| **Desvio padrão** | > 30% de mudança | Check outliers |
| **Nulls** | > 5% de mudança | Check validação Silver |
| **Min/Max** | Novos extremos | Check novo range |
| **Cardinality** | > 50% de mudança | Check novo valor |
| **Volume diário** | > 30% de mudança | Check fonte |

---

## Automação: Drift Detection Pipeline

### SQL Alert Task Agendado

```yaml
resources:
  jobs:
    drift_detection:
      name: "Daily Drift Detection"

      tasks:
        - task_key: detect_schema_drift
          sql_task:
            alert:
              alert_id: "schema-drift-detector"
            warehouse_id: "abc123"

        - task_key: detect_data_drift
          sql_task:
            alert:
              alert_id: "data-drift-detector"
            warehouse_id: "abc123"

      schedule:
        quartz_cron_expression: "0 3 * * ?"  # 3 AM diariamente
```

### Armazenar Resultados de Drift

```sql
-- Tabela de log de detecções de drift
CREATE TABLE IF NOT EXISTS catalog.quality.drift_log (
  drift_id STRING,
  table_name STRING,
  drift_type STRING,  -- SCHEMA | DATA
  change_type STRING,  -- COLUMN_ADD | COLUMN_DELETE | DISTRIBUTION_SHIFT | NULL_INCREASE | OUTLIER
  metric_name STRING,
  threshold_value DOUBLE,
  detected_value DOUBLE,
  percent_change DOUBLE,
  severity STRING,  -- INFO | WARNING | CRITICAL
  first_detected TIMESTAMP,
  last_detected TIMESTAMP,
  status STRING,  -- OPEN | INVESTIGATING | RESOLVED
  root_cause STRING,
  resolution_date DATE
);

-- Inserir detecção de schema drift
INSERT INTO catalog.quality.drift_log
VALUES (
  CONCAT('DRIFT_', CURRENT_TIMESTAMP_MS()),
  'silver_vendas',
  'SCHEMA',
  'COLUMN_ADD',
  'promo_code',
  NULL,
  NULL,
  NULL,
  'INFO',
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'OPEN',
  NULL,
  NULL
);
```

---

## Protocolo de Resposta

### Etapa 1: Alerta Dispara

```
Drift Detection SQL Alert Task
  ↓ Detecta mudança
  ↓ Envia notificação Teams/Email
  ↓ Cria ticket JIRA/Azure DevOps
```

### Etapa 2: Investigação

```sql
-- 1. Confirmar drift
SELECT * FROM catalog.quality.drift_log
WHERE status = 'OPEN'
ORDER BY first_detected DESC;

-- 2. Investigar lineage (schema drift)
-- Identificar qual arquivo/fonte causou mudança
SELECT
  _metadata.file_path,
  COUNT(*) AS record_count,
  CURRENT_TIMESTAMP() AS detected_at
FROM bronze_vendas
WHERE _metadata.file_path LIKE '%2026-04-09%'
GROUP BY _metadata.file_path;

-- 3. Investigar distribuição (data drift)
-- Comparar perfil hora-a-hora
SELECT
  HOUR(data_carga) AS hora,
  COUNT(*) AS records,
  ROUND(AVG(valor_total), 2) AS avg_valor,
  MIN(valor_total) AS min_valor,
  MAX(valor_total) AS max_valor
FROM silver_vendas
WHERE data_evento >= current_date()
GROUP BY HOUR(data_carga)
ORDER BY hora DESC;
```

### Etapa 3: Fix

| Tipo de Drift | Ação |
|---------------|------|
| **Schema Addition** | Aceitar (mergeSchema=true) ou bloquear (review owner) |
| **Schema Deletion** | Rejeitar pipeline, notificar source owner |
| **Type Change** | Manual fix em Bronze ou Silver expectations |
| **Distribution Shift** | Atualizar expectations/thresholds ou investigar fonte |
| **Null Increase** | Revis validação em Bronze, adjust expect_or_drop |
| **Outlier** | Investigar evento raro ou erro de entrada |

### Etapa 4: Validação + Fechamento

```sql
-- Validar que drift foi resolvido
SELECT
  drift_id,
  table_name,
  CASE
    WHEN detected_value IS NULL THEN 'RESOLVED: Coluna removida corretamente'
    WHEN ABS(percent_change) < 5 THEN 'RESOLVED: Drift normalizado'
    ELSE 'STILL_OPEN'
  END AS resolution_status
FROM catalog.quality.drift_log
WHERE status = 'INVESTIGATING'
  AND DATEDIFF(current_date(), first_detected) >= 1;

-- Atualizar log
UPDATE catalog.quality.drift_log
SET status = 'RESOLVED', resolution_date = current_date()
WHERE drift_id = 'DRIFT_...'
  AND DATEDIFF(current_date(), first_detected) >= 1;
```

---

## Checklist de Drift Detection

- [ ] SDP com `mergeSchema=true` configurado na Bronze
- [ ] Tabela `catalog.quality.schema_history` criada
- [ ] Comparação de schema automática agendada (diária)
- [ ] Tabela `catalog.quality.drift_log` criada e monitorada
- [ ] Thresholds de data drift definidos (20% avg, 30% volume, etc)
- [ ] SQL Alert Tasks para schema e data drift configuradas
- [ ] Runbook de investigação documentado
- [ ] Escalação para source owner definida
- [ ] Validação de resolução de drift implementada
- [ ] Dashboard de drift aberto/resolvido criado
