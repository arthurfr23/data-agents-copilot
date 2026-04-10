# Data Profiling: Protocolo de Qualidade

Dimensões de qualidade segundo framework DAMA. Quando executar, métricas a coletar, armazenamento de resultados.

---

## 6 Dimensões DAMA de Qualidade

| Dimensão | Definição | Métrica | Threshold |
|----------|-----------|---------|-----------|
| **Completude** | % de valores não-nulos em colunas obrigatórias | (COUNT NOT NULL / COUNT) × 100 | ≥ 95% |
| **Unicidade** | Ausência de duplicatas em PKs/chaves naturais | COUNT DISTINCT / COUNT | 100% |
| **Validade** | Conformidade com domínios esperados | CASE WHEN valor IN (...) | ≥ 98% |
| **Consistência** | Coerência entre tabelas relacionadas (FK) | COUNT sem par em dim | 100% |
| **Pontualidade** | Dados chegam dentro do SLA | MAX(data_carga) >= NOW - SLA_hours | Caso a caso |
| **Acurácia** | Conformidade com sistema de origem | Amostra vs Sistema Source | ≥ 99% |

---

## Protocolo de Profiling

### Quando Executar

| Cenário | Frequência |
|---------|-----------|
| **Novo datasource** | 1x ao ingerir pela primeira vez |
| **Schema change** | Imediatamente após alteração |
| **Volume increase** | Se volume cresce > 20% |
| **Refresh Regular** | Semanalmente em produção (Gold layer) |
| **Investigação de anomalia** | Ad hoc quando qualidade cai |

### Queries de Profiling Padrão

#### 1. Completude (Null %)

```sql
SELECT
  table_name,
  column_name,
  COUNT(*) AS total_rows,
  COUNT(column_name) AS non_null_rows,
  COUNT(*) - COUNT(column_name) AS null_count,
  ROUND(100.0 * (COUNT(*) - COUNT(column_name)) / COUNT(*), 2) AS null_percent,
  CASE
    WHEN 100.0 * (COUNT(*) - COUNT(column_name)) / COUNT(*) > 5
    THEN 'WARNING: >5% nulos'
    ELSE 'OK'
  END AS status
FROM catalog.schema.table
GROUP BY table_name, column_name
ORDER BY null_percent DESC;
```

#### 2. Unicidade (Duplicatas)

```sql
-- Chave Primária
SELECT
  table_name,
  'id_venda' AS column_name,
  COUNT(*) AS total_rows,
  COUNT(DISTINCT id_venda) AS distinct_rows,
  COUNT(*) - COUNT(DISTINCT id_venda) AS duplicate_count,
  CASE
    WHEN COUNT(*) = COUNT(DISTINCT id_venda)
    THEN 'OK: Sem duplicatas'
    ELSE 'ERROR: Duplicatas detectadas'
  END AS status
FROM catalog.schema.table
GROUP BY table_name;

-- Chave Natural (ex: email)
SELECT
  COUNT(*) AS total_rows,
  COUNT(DISTINCT email) AS distinct_emails,
  COUNT(*) - COUNT(DISTINCT email) AS duplicate_emails
FROM catalog.schema.clientes
HAVING COUNT(*) > COUNT(DISTINCT email);
```

#### 3. Validade (Domain Values)

```sql
SELECT
  table_name,
  'status' AS column_name,
  status AS value,
  COUNT(*) AS count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM catalog.schema.table), 2) AS percent
FROM catalog.schema.table
GROUP BY table_name, status
ORDER BY count DESC;

-- Verificar valores inválidos
SELECT COUNT(*) AS invalid_count
FROM catalog.schema.table
WHERE status NOT IN ('ATIVO', 'INATIVO', 'SUSPENSO')
  AND status IS NOT NULL;
```

#### 4. Consistência (Integridade Referencial)

```sql
-- Orphaned FKs (vendas sem cliente correspondente)
SELECT COUNT(*) AS orphaned_fks
FROM catalog.schema.vendas v
LEFT JOIN catalog.schema.clientes c ON v.id_cliente = c.id_cliente
WHERE c.id_cliente IS NULL
  AND v.id_cliente IS NOT NULL;

-- Verificar cobertura de dimensões
SELECT
  'dim_cliente' AS dimension,
  COUNT(DISTINCT id_cliente) AS dim_count,
  (SELECT COUNT(DISTINCT id_cliente) FROM catalog.schema.vendas) AS fact_unique_keys,
  CASE
    WHEN COUNT(DISTINCT id_cliente) >= (SELECT COUNT(DISTINCT id_cliente) FROM catalog.schema.vendas)
    THEN 'OK: Dimensão cobre fatos'
    ELSE 'WARNING: Fatos com clientes não em dimensão'
  END AS status
FROM catalog.schema.clientes;
```

#### 5. Pontualidade (Freshness)

```sql
SELECT
  table_name,
  MAX(data_evento) AS last_event_date,
  MAX(data_carga) AS last_load_time,
  CAST(current_timestamp() AS DATE) AS today,
  DATEDIFF(CAST(current_timestamp() AS DATE), MAX(data_evento)) AS days_since_last_event,
  CASE
    WHEN DATEDIFF(CAST(current_timestamp() AS DATE), MAX(data_evento)) > 2
    THEN 'ALERT: Dados atrasados > 2 dias'
    WHEN DATEDIFF(CAST(current_timestamp() AS DATE), MAX(data_evento)) = 1
    THEN 'OK: Atualizado ontem'
    ELSE 'OK: Atualizado hoje'
  END AS freshness_status
FROM catalog.schema.table
GROUP BY table_name;
```

#### 6. Distribuição (Min/Max/Avg)

```sql
SELECT
  'valor_total' AS column_name,
  COUNT(*) AS count,
  MIN(valor_total) AS min_value,
  MAX(valor_total) AS max_value,
  ROUND(AVG(valor_total), 2) AS avg_value,
  ROUND(STDDEV(valor_total), 2) AS stddev_value,
  ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY valor_total), 2) AS p25,
  ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY valor_total), 2) AS p50,
  ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY valor_total), 2) AS p75,
  ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY valor_total), 2) AS p95
FROM catalog.schema.vendas;
```

#### 7. Cardinalidade (Valores Únicos)

```sql
SELECT
  'categoria' AS column_name,
  COUNT(DISTINCT categoria) AS cardinality,
  COUNT(*) AS total_rows,
  ROUND(100.0 * COUNT(DISTINCT categoria) / COUNT(*), 2) AS cardinality_percent,
  CASE
    WHEN COUNT(DISTINCT categoria) / COUNT(*) > 0.5 THEN 'HIGH: Muitos valores únicos'
    WHEN COUNT(DISTINCT categoria) < 50 THEN 'LOW: Poucas categorias'
    ELSE 'MEDIUM'
  END AS cardinality_type
FROM catalog.schema.table;
```

---

## Armazenar Resultados de Profiling

### Tabela de Metadados

```sql
-- Criar tabela de profiling
CREATE TABLE IF NOT EXISTS catalog.quality.profiling_results (
  profiling_id STRING,
  table_name STRING,
  column_name STRING,
  profiling_date DATE,

  -- Completude
  null_count BIGINT,
  null_percent DOUBLE,

  -- Unicidade
  unique_count BIGINT,
  duplicate_count BIGINT,

  -- Distribuição
  min_value STRING,
  max_value STRING,
  avg_value DOUBLE,
  stddev_value DOUBLE,
  cardinality BIGINT,

  -- Status
  quality_score DOUBLE,
  status STRING,  -- OK, WARNING, ERROR
  notes STRING,

  created_at TIMESTAMP
);
```

### Executar Profiling Completo

```sql
-- Inserir resultados de profiling para bronze_vendas
INSERT INTO catalog.quality.profiling_results
SELECT
  CONCAT(table_name, '_', column_name, '_', current_date()),
  table_name,
  column_name,
  current_date(),
  COUNT(*) - COUNT(column_name),  -- null_count
  ROUND(100.0 * (COUNT(*) - COUNT(column_name)) / COUNT(*), 2),  -- null_percent
  COUNT(DISTINCT column_name),  -- unique_count
  0,  -- duplicate_count (simplificado)
  CAST(MIN(column_name) AS STRING),  -- min_value
  CAST(MAX(column_name) AS STRING),  -- max_value
  ROUND(AVG(CAST(column_name AS DOUBLE)), 2),  -- avg_value
  NULL,  -- stddev_value
  COUNT(DISTINCT column_name),  -- cardinality
  CASE
    WHEN 100.0 * (COUNT(*) - COUNT(column_name)) / COUNT(*) > 5 THEN 0.7
    ELSE 0.9
  END,  -- quality_score
  CASE
    WHEN 100.0 * (COUNT(*) - COUNT(column_name)) / COUNT(*) > 5 THEN 'WARNING'
    ELSE 'OK'
  END,  -- status
  NULL,  -- notes
  current_timestamp()
FROM bronze_vendas
GROUP BY table_name, column_name;
```

### Query de Dashboard

```sql
-- Dashboard: Resumo de qualidade por tabela
SELECT
  table_name,
  COUNT(*) AS total_columns_profiled,
  ROUND(AVG(quality_score), 2) AS avg_quality_score,
  COUNTIF(status = 'ERROR') AS error_count,
  COUNTIF(status = 'WARNING') AS warning_count,
  MAX(profiling_date) AS last_profiling_date,
  CASE
    WHEN AVG(quality_score) >= 0.95 THEN 'EXCELLENT'
    WHEN AVG(quality_score) >= 0.85 THEN 'GOOD'
    WHEN AVG(quality_score) >= 0.75 THEN 'FAIR'
    ELSE 'POOR'
  END AS overall_quality
FROM catalog.quality.profiling_results
WHERE profiling_date >= current_date() - 7
GROUP BY table_name
ORDER BY avg_quality_score DESC;
```

---

## Checklist de Implementação

- [ ] Tabela `catalog.quality.profiling_results` criada
- [ ] Profiling executado para novas sources
- [ ] Queries de 7 dimensões (completude, unicidade, etc) testadas
- [ ] Resultados armazenados em metadados
- [ ] Thresholds de qualidade definidos por tabela
- [ ] Dashboard de qualidade criado
- [ ] Alertas configurados para WARNING/ERROR
- [ ] Profiling regular agendado (semanal para Gold)
- [ ] Documentação de anomalias em sistema de tickets
- [ ] Runbooks de remediação escritos
