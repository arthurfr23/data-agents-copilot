# SDP LakeFlow Rules — Spark Declarative Pipelines (Regras Mandatórias)

**Último update:** 2026-04-09
**Domínio:** Pipelines declarativos Spark (SDP/LakeFlow)
**Plataformas:** Databricks 12.2+, Azure Fabric

---

## Regra 1: API Moderna — Nunca Use DLT Legada

### ✅ CORRETO (SDP)
```python
from pyspark import pipelines as dp

# Definir transformação
@dp.table
def bronze_raw_sales():
    return spark.readStream.option("cloudFiles", "s3://bucket/sales/") \
        .schema("id BIGINT, value DECIMAL(10,2)") \
        .load()

@dp.table
def silver_sales():
    return dp.read_stream("bronze_raw_sales") \
        .filter("value > 0") \
        .select("id", "value")
```

### ❌ ERRADO (DLT Legada)
```python
import dlt
from pyspark.sql.functions import *

@dlt.table
def bronze_raw_sales():
    return spark.readStream...
```

**Por quê?**
- DLT é API legada (descontinuada em 2024)
- SDP oferece melhor performance, melhor UI, melhor observabilidade
- SDP suporta Expectativas (data quality) nativas

---

## Regra 2: Operações DDL — CREATE OR REFRESH, Nunca REPLACE

### ✅ CORRETO
```sql
CREATE OR REFRESH STREAMING TABLE silver_sales AS
SELECT id, value FROM stream(bronze_raw_sales);
```

### ❌ ERRADO
```sql
CREATE OR REPLACE TABLE silver_sales AS
SELECT id, value FROM stream(bronze_raw_sales);
```

**Diferença:**
| Operação      | Comportamento                                         | Efeito                      |
|---------------|-------------------------------------------------------|---------------------------|
| CREATE (novo) | Se não existe, cria                                   | Cria nova tabela          |
| CREATE EXISTS | Erro se já existe                                     | Não idempotente           |
| CREATE OR REFRESH | Se existe, atualiza; se não, cria (idempotente)   | ✅ Usa SDP semantics      |
| CREATE OR REPLACE | Deleta e recria (perde histórico Delta Time Travel) | ❌ Perde dados           |

---

## Regra 3: Camadas Medallion — STREAMING TABLE vs MATERIALIZED VIEW

### Bronze Layer — Auto Loader com cloud_files

```sql
-- SQL
CREATE OR REFRESH STREAMING TABLE bronze_sales AS
SELECT
  *,
  _metadata.file_path,
  _metadata.file_modification_time
FROM cloud_files(
  "s3://bucket/sales/",
  "parquet",
  map("cloudFiles.format" → "parquet")
);
```

```python
# Python (SDP)
from pyspark import pipelines as dp

@dp.table
def bronze_sales():
    return spark.readStream.option("cloudFiles", "s3://bucket/sales/") \
        .option("cloudFiles.format", "parquet") \
        .load()
```

**Regra:** Sempre `cloud_files()` (SQL) ou `cloudFiles` (Python). Nunca manualmente iterar arquivos.

---

### Silver Layer — STREAMING TABLE com stream()

```sql
-- ✅ CORRETO: STREAMING TABLE para dados em movimento
CREATE OR REFRESH STREAMING TABLE silver_sales AS
SELECT
  id,
  value,
  CURRENT_TIMESTAMP() AS processed_at
FROM stream(bronze_sales)  -- ← stream() obrigatório
WHERE value > 0;
```

```sql
-- ❌ ERRADO: MATERIALIZED VIEW em Silver
CREATE OR REFRESH MATERIALIZED VIEW silver_sales AS
SELECT * FROM bronze_sales;  -- Vai tentar full scan, não stream
```

**Por quê?**
- STREAMING TABLE = otimizado para incremental (somente novos dados)
- MATERIALIZED VIEW = full materialization (mais lento em Silver)
- stream() keyword = garante lineage e incremental processing

---

### Gold Layer — MATERIALIZED VIEW para Agregações Finais

```sql
-- ✅ CORRETO: MATERIALIZED VIEW em Gold (agregações finais)
CREATE OR REFRESH MATERIALIZED VIEW gold_sales_daily AS
SELECT
  DATE(processed_at) AS data,
  COUNT(*) AS num_transacoes,
  SUM(value) AS valor_total,
  AVG(value) AS valor_medio
FROM stream(silver_sales)  -- Ler de Silver stream
GROUP BY DATE(processed_at);
```

**Por quê?**
- MATERIALIZED VIEW = agregação completa, schema final
- Gold é consumida por BI (não precisa de streaming)
- GROUP BY + agregações = MATERIALIZED VIEW padrão

---

## Regra 4: SCD2 (Type 2) — Sempre Use AUTO CDC, Nunca Implemente Manual

### ✅ CORRETO — AUTO CDC (SQL)

```sql
-- Silver: CDC automático detecta mudanças
CREATE OR REFRESH STREAMING TABLE silver_customers_cdc AS
SELECT
  id,
  name,
  email,
  _change_type,  -- INSERT, UPDATE_PREIMAGE, UPDATE_POSTIMAGE, DELETE
  _commit_version,
  _commit_timestamp
FROM cdc_read_changes(
  initial_data_source => table("bronze_customers"),
  ignore_deletes => false,
  ignore_column_droppped => false
);

-- Gold: SCD2 aplicado automaticamente
CREATE OR REFRESH MATERIALIZED VIEW gold_customers_scd2 AS
SELECT
  id,
  name AS current_name,
  LAG(name) OVER (PARTITION BY id ORDER BY _commit_version) AS previous_name,
  _commit_timestamp AS effective_from,
  LEAD(_commit_timestamp) OVER (PARTITION BY id ORDER BY _commit_version)
    - INTERVAL 1 SECOND AS effective_to,
  ROW_NUMBER() OVER (PARTITION BY id ORDER BY _commit_version) AS version_number
FROM silver_customers_cdc
WHERE _change_type IN ('UPDATE_POSTIMAGE', 'INSERT');
```

### ✅ CORRETO — AUTO CDC (Python SDP)

```python
from pyspark import pipelines as dp
from pyspark.sql.functions import *

@dp.table
def silver_customers_cdc():
    return dp.create_auto_cdc_flow(
        source=dp.read_stream("bronze_customers"),
        target="silver_customers_cdc",
        keys=["id"],  # Primary key
        sequence_by="_commit_timestamp"  # Ordering column
    )

@dp.materialized_view
def gold_customers_scd2():
    df = dp.read_stream("silver_customers_cdc")
    return df.select(
        "id",
        col("name").alias("current_name"),
        col("__START_AT").alias("effective_from"),
        col("__END_AT").alias("effective_to")
    )
```

### ❌ ERRADO — SCD2 Manual com LAG/LEAD

```python
# NÃO FAÇA ISTO:
from pyspark.sql.functions import lag, lead, row_number
from pyspark.sql.window import Window

# Anti-pattern: implementação manual de SCD2
@dp.table
def silver_customers():
    df = dp.read_stream("bronze_customers")
    window = Window.partitionBy("id").orderBy("update_timestamp")

    return df.select(
        "id",
        col("name").alias("current_name"),
        lag("name").over(window).alias("previous_name"),  # ← Manual, propenso a bug
        col("update_timestamp").alias("effective_from"),
        lead(col("update_timestamp")).over(window).alias("effective_to")
    )
```

**Por quê não?**
- Manual SCD2 com LAG/LEAD é propenso a erros (off-by-one, null handling)
- AUTO CDC detecta deletions e inserts corretamente
- Databricks garante ordem com `__START_AT` e `__END_AT` (double underscore)

---

## Regra 5: Expectations — Data Quality Nativa em SDP

```python
from pyspark import pipelines as dp

@dp.expect("valid_id", "id > 0")  # Falhar se id <= 0
@dp.expect_or_drop("non_null_email", "email IS NOT NULL")  # Drop rows com email nulo
@dp.table
def silver_customers():
    return dp.read_stream("bronze_customers") \
        .filter("id > 0")
```

**Ou em SQL:**

```sql
CREATE OR REFRESH STREAMING TABLE silver_customers
EXPECT valid_id, non_null_email AS
SELECT
  id,
  COALESCE(email, 'NO_EMAIL') AS email
FROM stream(bronze_customers)
WHERE id > 0;
```

---

## Regra 6: Multi-Schema — Um Pipeline, Múltiplos Schemas

```python
# ✅ RECOMENDADO: Um pipeline escrevendo bronze_*, silver_*, gold_*
from pyspark import pipelines as dp

@dp.table
def bronze_customers():
    return spark.readStream.option("cloudFiles", "s3://bucket/customers/").load()

@dp.table
def bronze_orders():
    return spark.readStream.option("cloudFiles", "s3://bucket/orders/").load()

@dp.table
def silver_customers():
    return dp.read_stream("bronze_customers").filter("id > 0")

@dp.table
def silver_orders():
    return dp.read_stream("bronze_orders").filter("order_id > 0")

@dp.materialized_view
def gold_sales():
    customers = dp.read_stream("silver_customers")
    orders = dp.read_stream("silver_orders")
    return customers.join(orders, "id")
```

**Vantagem:** Lineage clara, um DAG, observabilidade unificada.

---

## Regra 7: Sem Notebooks em Pipeline Code

### ❌ ERRADO
```
Pipeline: sales_pipeline
  ├─ Notebook: /Users/analyst/cleanup.py
  ├─ Notebook: /Users/analyst/transform.py
  └─ Notebook: /Users/analyst/load.py
```

### ✅ CORRETO
```
Repository: data-pipelines/
  └─ sales_pipeline.py (SDP com todas as transformações)

Pipeline: sales_pipeline
  └─ job: Executar sales_pipeline.py
```

**Por quê?**
- Notebooks = contexto de trabalho (não reproducível)
- Código SDP = reproducível, versionável em Git
- Debugging mais fácil

---

## Gotchas e Best Practices

| Gotcha                              | Solução                                         |
|-------------------------------------|-------------------------------------------------|
| STREAMING TABLE sem stream()        | Sempre usar stream(tabela_anterior)             |
| CREATE OR REPLACE em Gold           | Usar CREATE OR REFRESH (preserva Time Travel)  |
| SCD2 manual com lógica complexa      | Usar AUTO CDC (dp.create_auto_cdc_flow)        |
| Expectations não validam dados      | Expectations são warnings apenas (log data quality)|
| Migrando de DLT para SDP            | Usar `dlt.on_attach` → SDP (gradual)           |
