# Performance Best Practices — Otimizações Spark

**Último update:** 2026-04-09
**Domínio:** Performance de processamento, tuning de spark
**Plataformas:** Databricks, Azure Fabric

---

## DataFrame API vs RDD API

### ✅ CORRETO: DataFrame API (Otimizado)

```python
from pyspark.sql.functions import col, sum, count

# DataFrame: Catalyst optimizer
df = spark.read.format("delta").load("/dbfs/user/hive/warehouse/fact_vendas")
result = df.groupBy("regiao").agg(
    sum("valor").alias("total_vendas"),
    count("*").alias("num_transacoes")
)
```

### ❌ ERRADO: RDD API (Sem Otimização)

```python
# RDD: Sem otimização pelo Catalyst
rdd = spark.sparkContext.textFile("s3://bucket/data.csv")
result = rdd.map(lambda x: x.split(",")) \
    .filter(lambda x: len(x) > 5) \
    .map(lambda x: (x[0], float(x[4]))) \
    .reduceByKey(lambda x, y: x + y)  # Sem otimização de índice
```

**Performance:** DataFrame é 5-100x mais rápido (Catalyst otimiza plano de execução).

---

## UDF vs Native Functions

### ❌ ERRADO: UDF Custom

```python
from pyspark.sql.functions import udf
from pyspark.sql.types import DoubleType

# UDF: Sem otimização, executa em Python (lento)
@udf(returnType=DoubleType())
def calculate_discount(valor, taxa):
    if valor > 1000:
        return valor * (1 - taxa * 0.15)  # 15% desconto extra
    return valor * (1 - taxa)

df_vendas = df_vendas.withColumn(
    "valor_final",
    calculate_discount(col("valor"), col("taxa_desconto"))
)
```

**Performance:** UDF em Python = 50-100x mais lento (serialização Python).

### ✅ CORRETO: Native Function

```python
from pyspark.sql.functions import col, when, round

# Native: Otimizado pelo Catalyst
df_vendas = df_vendas.withColumn(
    "valor_final",
    round(
        when(col("valor") > 1000, col("valor") * (1 - col("taxa_desconto") * 0.15))
        .otherwise(col("valor") * (1 - col("taxa_desconto"))),
        2
    )
)
```

**Performance:** Native é 50-100x mais rápido (execução em Spark).

---

## broadcast() — Joins com Tabelas Pequenas

### Padrão: Tabela < 100MB

```python
from pyspark.sql.functions import broadcast

# Tabela grande
df_vendas = spark.read.format("delta").load("/warehouse/fact_vendas")  # 10GB

# Tabela pequena
df_categoria = spark.read.format("delta").load("/warehouse/dim_categoria")  # 50MB

# ✅ CORRETO: Broadcast tabela pequena
result = df_vendas.join(
    broadcast(df_categoria),  # ← Enviar para todos workers
    on="id_categoria",
    how="inner"
)
```

**Benefício:** Enviar tabela pequena aos workers via broadcast (vs shuffle toda a grande).

### Quando NÃO Usar broadcast()

```python
# ❌ Tabela grande > 100MB: não faz broadcast (OOM)
df_grande = spark.read.format("delta").load("/warehouse/tabela_1gb")
df_outro = spark.read.format("delta").load("/warehouse/outra_10gb")

# Deixar Spark decidir (não forçar broadcast)
result = df_grande.join(df_outro, on="id", how="inner")
```

---

## repartition() vs coalesce()

### repartition() — Aumentar Partições (com Shuffle)

```python
# DataFrame tem 8 partições, quer 200 para processing paralelo
df = spark.read.format("delta").load("/warehouse/fact_vendas")

repartitioned = df.repartition(200)  # ← Shuffles dados (I/O alto)
```

**Use para:** Transformações complexas após join (aumentar paralelismo).

**Custo:** Full shuffle (alto overhead I/O e rede).

### coalesce() — Reduzir Partições (sem Shuffle)

```python
# DataFrame tem 200 partições, quer escrever em 8 arquivos
result_df = df.groupBy("regiao").count()  # Retorna 8 partições

coalesced = result_df.coalesce(8)  # ← Mergi localmente (sem shuffle)

coalesced.write \
    .format("delta") \
    .mode("overwrite") \
    .save("/warehouse/resultado")
```

**Use para:** Reduzir partições antes de escrever (merge local).

**Vantagem:** Sem shuffle (menos I/O).

---

## cache() vs persist()

### cache() — Default (MEMORY_AND_DISK)

```python
df = spark.read.format("delta").load("/warehouse/fact_vendas")

# Usar 2x em transformações diferentes
result1 = df.filter("regiao == 'SP'").count()
result2 = df.filter("regiao == 'RJ'").count()

# ❌ ERRADO: Lê arquivo 2x (ineficiente)
# ✅ CORRETO: Cache após primeira leitura
df.cache()  # ← Reter na memória + disco se necessário
result1 = df.filter("regiao == 'SP'").count()  # Usa cache
result2 = df.filter("regiao == 'RJ'").count()  # Usa cache
```

### persist() — Controlar Storage Level

```python
from pyspark import StorageLevel

df = spark.read.format("delta").load("/warehouse/fact_vendas")

# MEMORY_AND_DISK: default
df.persist(StorageLevel.MEMORY_AND_DISK)

# DISK_ONLY: usar apenas disco (menos memória)
df.persist(StorageLevel.DISK_ONLY)

# MEMORY_ONLY: risco OOM se não caber
df.persist(StorageLevel.MEMORY_ONLY)
```

### Remover Cache

```python
# Liberar memória
df.unpersist()
```

---

## Adaptive Query Execution (AQE)

### Ativado por Default (Databricks 7.3+)

```python
# Spark ajusta paralelismo dinamicamente durante execução
spark.conf.get("spark.sql.adaptive.enabled")  # True por default
```

**Benefícios:**
- Ajusta número de shuffle partitions baseado em dados reais
- Converte join strategy se tabela menor que threshold
- Coalesce partições vazias

**Não requer código, ativa automático.**

---

## Predicate Pushdown — Filtrar Antes de Join

### ❌ ERRADO: Join Primeiro, Depois Filtrar

```python
# 1. Join (10GB x 2GB)
joined = df_large.join(df_medium, on="id")  # ← 20GB resultado intermediário

# 2. Filtrar (reduz para 500MB)
result = joined.filter("regiao == 'SP'")
```

**Problema:** Join processa 20GB, depois filtra para 500MB (desperdício).

### ✅ CORRETO: Filtrar Primeiro, Depois Join

```python
# 1. Filtrar (2GB → 500MB)
df_large_filtered = df_large.filter("regiao == 'SP'")  # ← Reduz antes

# 2. Join (500MB x 2GB)
result = df_large_filtered.join(df_medium, on="id")
```

**Vantagem:** Join em 500MB ao invés de 20GB (10x mais rápido).

**Nota:** Catalyst otimiza automaticamente em muitos casos, mas explícito é melhor.

---

## collect() — Evitar em DataFrames Grandes

### ❌ ERRADO: collect() em 10GB

```python
# Traz 10GB para driver memory (crash)
df_grande = spark.read.format("delta").load("/warehouse/fact_vendas")  # 10GB
all_rows = df_grande.collect()  # ← OutOfMemory!
```

### ✅ CORRETO: Processar em Batches

```python
# Processar em microbatch no executor
def process_batch(pdf):
    print(f"Batch: {len(pdf)} linhas")
    return pdf

df_grande.mapInPandas(process_batch, schema=df_grande.schema).collect()

# Ou usar foreachBatch em streaming
query = df_grande.writeStream \
    .foreachBatch(lambda df, epoch: print(f"Batch {epoch}: {df.count()} rows")) \
    .start()
```

### Quando collect() é OK

```python
# Menos de 1GB em memória = seguro
small_result = df.filter("...").select("...").collect()  # OK se < 1GB
```

---

## Shuffle Partition Tuning

### Default: 200 (Databricks Default)

```python
spark.conf.get("spark.sql.shuffle.partitions")  # 200

# Para cluster com 256 cores, 200 pode ser baixo
# Aumentar para 512-1024 para melhor paralelismo
spark.conf.set("spark.sql.shuffle.partitions", "512")
```

### Ajuste Baseado em Dados

| Tamanho de Dados | Partições Recomendadas |
|-----------------|------------------------|
| < 1GB           | 4-8                    |
| 1-10GB          | 16-32                  |
| 10-100GB        | 64-128                 |
| 100-1000GB      | 256-512                |
| > 1000GB        | 512-2048               |

```python
# Ajuste dinâmico
total_size_gb = spark.sql("SELECT SUM(bytes) / 1e9 FROM tbl").collect()[0][0]
num_partitions = max(4, min(2048, int(total_size_gb / 0.5)))  # 0.5GB por partição
spark.conf.set("spark.sql.shuffle.partitions", str(num_partitions))
```

---

## Evitar Anti-Patterns

### 1. Select *

```python
# ❌ ERRADO: Lê todas colunas
df.select("*")

# ✅ CORRETO: Selecione apenas necessário
df.select("id", "valor", "regiao")
```

### 2. Multiple Passes (sem cache)

```python
# ❌ ERRADO: Relê arquivo 3x
count_vendas = df.count()
count_clientes = df.select("id_cliente").distinct().count()
sum_valores = df.agg(sum("valor")).collect()[0][0]

# ✅ CORRETO: Uma pass com múltiplas agregações
result = df.agg(
    count("*").alias("count_vendas"),
    countDistinct("id_cliente").alias("count_clientes"),
    sum("valor").alias("sum_valores")
)
```

### 3. Nested Loops

```python
# ❌ ERRADO: Nested loop = O(n²)
for categoria in categorias:
    df.filter(f"categoria == '{categoria}'").write.save(...)  # Escreve 100x

# ✅ CORRETO: Single pass com window
df.repartition("categoria").write.partitionBy("categoria").save(...)
```

---

## Gotchas

| Gotcha                              | Solução                                      |
|-------------------------------------|--------------------------------------------|
| UDF mais lento que native           | Usar pyspark.sql.functions                 |
| collect() causa OOM                 | Usar mapInPandas ou foreachBatch           |
| Cache > 30GB = memory pressure      | Usar persist(DISK_ONLY) ou coalesce       |
| broadcast() > 256MB = falha         | Usar join sem broadcast (let Spark decide) |
| Shuffle partitions default=200      | Ajustar baseado em tamanho de dados        |
