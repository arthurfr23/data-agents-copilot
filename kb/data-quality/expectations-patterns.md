# Expectations: Padrões SDP/LakeFlow

Validação de dados em pipelines via decoradores @dp.expect, @dp.expect_or_drop, @dp.expect_or_fail.

---

## Três Níveis de Expectativas

| Nível | Comportamento | Uso | Exemplo |
|-------|---------------|-----|---------|
| **@dp.expect** | Alerta apenas, continua pipeline | Bronze, alertas | `@expect(condition = "col IS NOT NULL")` |
| **@dp.expect_or_drop** | Remove registros inválidos | Silver, limpeza | `@expect_or_drop(condition = "valor > 0")` |
| **@dp.expect_or_fail** | Bloqueia pipeline se falhar | Gold, crítico | `@expect_or_fail(condition = "COUNT(*) > 1000")` |

---

## Estratégia por Camada

### Bronze: expect (alerta apenas)

```python
# Python SDP
from pyspark import pipelines as dp

@dp.table(name="bronze_vendas")
@dp.expect("col('id_venda').isNotNull()", "id_venda deve existir")
@dp.expect("col('data_evento').isNotNull()", "data_evento é obrigatória")
def bronze_vendas():
    return spark.readStream.format("cloudFiles") \
        .option("cloudFiles.format", "json") \
        .load("/Volumes/raw/vendas/")
```

**Comportamento:** Se expectativa falhar, registra no log mas continua a ingerir dados.

### Silver: expect_or_drop (remove inválidos)

```python
@dp.table(name="silver_vendas")
@dp.expect_or_drop("col('id_cliente').isNotNull()", "Remover vendas sem cliente")
@dp.expect_or_drop("col('valor_total') > 0", "Remover vendas com valor negativo")
@dp.expect_or_drop("col('data_evento').isNotNull()", "Remover eventos sem data")
def silver_vendas():
    return spark.read.table("bronze_vendas") \
        .filter(col("valor_total").isNotNull())
```

**Comportamento:** Registros que falham a validação são filtrados silenciosamente. Pipeline continua.

### Gold: expect_or_fail (bloqueia)

```python
@dp.materialized_view(name="gold_fact_vendas")
@dp.expect_or_fail("count(*) > 1000", "Fact deve ter mínimo 1000 linhas")
@dp.expect_or_fail("sum(valor_total) > 0", "Receita total deve ser positiva")
def gold_fact_vendas():
    return spark.read.table("silver_vendas") \
        .join(...).groupBy(...)
```

**Comportamento:** Se expectativa falha, pipeline para imediatamente. Requer investigação.

---

## SQL Syntax (SDP SQL)

### Bronze

```sql
CREATE OR REFRESH STREAMING TABLE bronze_clientes
CLUSTER BY (id_cliente)
AS
-- Expectativas apenas alertam
SELECT *
FROM STREAM read_files('/Volumes/raw/clientes/', format => 'json')
WHERE id_cliente IS NOT NULL;  -- Mínima filtragem

EXPECT (id_cliente IS NOT NULL) AS id_cliente_present;
EXPECT (email IS NOT NULL) AS email_present;
```

### Silver

```sql
CREATE OR REFRESH STREAMING TABLE silver_clientes
CLUSTER BY (id_cliente)
AS
SELECT
  id_cliente,
  CAST(nome AS STRING) AS nome,
  CAST(email AS STRING) AS email,
  CAST(data_criacao AS DATE) AS data_criacao
FROM stream(bronze_clientes)

-- expect_or_drop: remove registros inválidos
EXPECT OR DROP (id_cliente IS NOT NULL) AS id_cliente_not_null;
EXPECT OR DROP (email LIKE '%@%.%') AS email_valid;
EXPECT OR DROP (YEAR(data_criacao) >= 2010) AS data_valid;
```

### Gold

```sql
CREATE OR REFRESH MATERIALIZED VIEW gold_dim_cliente
CLUSTER BY (surrogate_key)
AS
SELECT
  ROW_NUMBER() OVER (ORDER BY id_cliente) AS surrogate_key,
  id_cliente,
  nome,
  email
FROM silver_clientes

-- expect_or_fail: bloqueia se condição falha
EXPECT OR FAIL (COUNT(*) > 100) AS min_rows;
EXPECT OR FAIL (COUNT(DISTINCT id_cliente) = COUNT(*)) AS no_duplicates;
```

---

## SQL Alert Tasks: Verificação no DAG

### Conceito
SQL Alert Tasks são tasks nativas em Databricks Jobs que executam condições SQL **dentro do DAG**. Se a condição falha, o job para antes de executar tasks downstream.

### Setup Passo-a-Passo

#### 1. Criar SQL Alert no Databricks SQL Editor

```sql
-- Salvar como Alert: "check_silver_volume"
SELECT COUNT(*)
FROM silver_vendas
WHERE date(data_carga) = current_date()
HAVING COUNT(*) < 1000  -- Se falhar, alerta dispara
```

Isso gera um `alert_id` reutilizável.

#### 2. Configurar no DABs (databricks.yml)

```yaml
resources:
  jobs:
    gold_pipeline:
      name: "Gold Pipeline com Quality Checks"

      tasks:
        # Task 1: Verificar volume de dados na Silver
        - task_key: check_silver_volume
          sql_task:
            alert:
              alert_id: "550e8400e29b41d4a716446655440000"  # UUID do alert criado
              pause_subscriptions: false  # Continuar enviando emails
            warehouse_id: "abc123xyz"

        # Task 2: Build Gold (depende de check_silver_volume)
        - task_key: build_gold_vendas
          depends_on:
            - task_key: check_silver_volume
          run_if: "ALL_SUCCESS"  # Só executa se check passou
          notebook_task:
            notebook_path: ../src/gold_vendas

        # Task 3: Validar Gold
        - task_key: check_gold_quality
          depends_on:
            - task_key: build_gold_vendas
          sql_task:
            alert:
              alert_id: "660e8400e29b41d4a716446655440001"
            warehouse_id: "abc123xyz"

        # Task 4: Downstream (só executa se tudo passou)
        - task_key: notify_success
          depends_on:
            - task_key: check_gold_quality
          run_if: "ALL_SUCCESS"
          notebook_task:
            notebook_path: ../src/notify
```

### Exemplos de Alertas

```sql
-- Alert 1: Verificar volume mínimo
SELECT COUNT(*)
FROM silver_vendas
WHERE date(data_carga) = current_date()
HAVING COUNT(*) < 500;  -- Falha se < 500 linhas

-- Alert 2: Verificar duplicatas
SELECT COUNT(*) - COUNT(DISTINCT id_venda)
FROM silver_vendas
HAVING COUNT(*) - COUNT(DISTINCT id_venda) > 0;  -- Falha se há duplicatas

-- Alert 3: Validar freshness
SELECT MAX(data_evento)
FROM silver_vendas
HAVING MAX(data_evento) < current_date() - 1;  -- Falha se dados atrasados

-- Alert 4: Integridade referencial
SELECT COUNT(*)
FROM silver_vendas v
LEFT JOIN silver_cliente c ON v.id_cliente = c.id_cliente
WHERE c.id_cliente IS NULL;  -- Falha se há orphaned FKs
```

---

## Padrão Recomendado: Dupla Camada

Combine **SQL Alert Tasks** (Jobs DAG) + **@dp.expect_or_fail** (Pipeline) para máxima proteção:

```yaml
resources:
  pipelines:
    silver_pipeline:
      transformations: "sql/**"
      # SQL dentro do pipeline tem expect_or_fail

  jobs:
    gold_orchestration:
      tasks:
        # Camada 1: Validação no DAG (SQL Alert Task)
        - task_key: validate_silver
          sql_task:
            alert:
              alert_id: "abc123"

        # Camada 2: Executa pipeline (que tem expect_or_fail)
        - task_key: run_gold_pipeline
          depends_on:
            - task_key: validate_silver
          pipeline_task:
            pipeline_id: "${resources.pipelines.gold_pipeline.id}"
```

**Benefício:** Falha rápida em dados ruins antes de gastar créditos com pipeline.

---

## Configuração de Nomes e Convenções

### Naming Pattern para Expectations

```sql
-- Pattern: [TABLE]_[DIMENSION]_[RULE]
EXPECT OR DROP (id_cliente IS NOT NULL)
  AS silver_cliente_id_not_null;

EXPECT OR FAIL (valor_total > 0)
  AS gold_fact_valor_positive;

EXPECT OR DROP (email LIKE '%@%.%')
  AS silver_cliente_email_format;
```

### Armazenar Resultados de Expectativas

```sql
-- Opcional: criar tabela de metadados
CREATE TABLE IF NOT EXISTS catalog.quality.expectation_results (
  expectation_id STRING,
  table_name STRING,
  rule_name STRING,
  pass_count BIGINT,
  fail_count BIGINT,
  fail_percent DOUBLE,
  created_at TIMESTAMP
);

-- Log a cada execução
INSERT INTO catalog.quality.expectation_results
SELECT
  'bronze_vendas_id_not_null',
  'bronze_vendas',
  'id_venda IS NOT NULL',
  SUM(CASE WHEN id_venda IS NOT NULL THEN 1 ELSE 0 END),
  SUM(CASE WHEN id_venda IS NULL THEN 1 ELSE 0 END),
  ROUND(100.0 * SUM(CASE WHEN id_venda IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2),
  current_timestamp()
FROM bronze_vendas;
```

---

## Checklist de Implementação

- [ ] Bronze tem @dp.expect (alerta apenas)
- [ ] Silver tem @dp.expect_or_drop em TODAS as validações
- [ ] Gold tem @dp.expect_or_fail em métricas críticas
- [ ] SQL Alerts criados no Databricks SQL Editor
- [ ] SQL Alert Tasks configuradas no DABs
- [ ] Dupla camada de validação implementada (Job + Pipeline)
- [ ] Nomes de expectations seguem padrão [TABLE]_[DIMENSION]_[RULE]
- [ ] Alertas de email configurados (pause_subscriptions em dev)
- [ ] Resultados de expectations logados em metadados
- [ ] Runbooks de remediação documentados
