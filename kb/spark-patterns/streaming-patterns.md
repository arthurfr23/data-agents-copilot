# Streaming Patterns — Spark Structured Streaming

**Último update:** 2026-04-09
**Domínio:** Processamento contínuo de dados, triggers, checkpoints
**Plataformas:** Databricks, Azure Fabric

---

## Trigger Modes — Três Estratégias de Acionamento

### 1. availableNow — Batch-Like (Recomendado para Pipelines)

```python
from pyspark.sql import *

df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "sales_events") \
    .load()

query = df.writeStream \
    .format("delta") \
    .mode("append") \
    .option("checkpointLocation", "/tmp/ckpt/kafka_sales") \
    .trigger(availableNow=True)  # ← Processa tudo disponível, depois para
    .start()

query.awaitTermination()  # Aguarda conclusão
```

**Comportamento:** Processa todos os dados disponíveis, para, aguarda próxima execução.

**Use para:** Pipelines em batch (jobcluster diário), processar pendências.

---

### 2. processingTime — Micro-Batch (Padrão de Latência Baixa)

```python
query = df.writeStream \
    .format("delta") \
    .mode("append") \
    .option("checkpointLocation", "/tmp/ckpt/kafka_sales") \
    .trigger(processingTime="10 seconds")  # ← A cada 10s, processa
    .start()

# Nunca usar awaitTermination() — query rode infinitamente
```

**Comportamento:** A cada intervalo (10s), processa microbatch de dados disponíveis.

**Use para:** Streams contínuos (latência 10-60s aceitável), dashboards ao vivo.

---

### 3. continuous — Experimental (Evite em Produção)

```python
query = df.writeStream \
    .format("delta") \
    .mode("append") \
    .option("checkpointLocation", "/tmp/ckpt/kafka_sales") \
    .trigger(continuous="1 second")  # ← Processamento contínuo
    .start()
```

**Comportamento:** Processamento verdadeiramente contínuo (sub-segundo).

**Problema:** Experimental, não suportado para todas as operações (joins, agregações).

**Use para:** Casos muito específicos (raramente).

---

## Auto Loader — Ingestão de Arquivos Incremental

### Padrão Recomendado

```python
# Bronze: Auto Loader com cloudFiles
df = spark.readStream \
    .format("cloudFiles") \
    .option("cloudFiles.format", "parquet") \
    .option("cloudFiles.schemaLocation", "/tmp/schema_inference") \
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns") \
    .load("s3://bucket/incoming/sales/")

query = df.writeStream \
    .format("delta") \
    .mode("append") \
    .option("checkpointLocation", "/tmp/ckpt/bronze_sales") \
    .trigger(processingTime="5 minutes") \
    .start("/dbfs/user/hive/warehouse/bronze_sales")
```

**Vantagens:**
- Auto descobre novos arquivos
- Schema inference automática
- Schema evolution (adiciona novas colunas)
- Checkpointing automático

---

## Checkpoint — Rastreamento de Progresso

### Regra Crítica: Nunca Deletar Checkpoint

```python
# ❌ ERRADO
import os
os.remove("/tmp/ckpt/bronze_sales/_delta_log")  # NUNCA!

# Efeito: Stream recomeça do zero, reprocessa TUDO
```

### Checkpoint Isolado por Stream

```python
# Cada stream tem seu próprio checkpoint
query_kafka = spark.readStream \
    .format("kafka") \
    .load() \
    .writeStream \
    .option("checkpointLocation", "/tmp/ckpt/kafka_stream") \  # ← Isolado
    .start()

query_files = spark.readStream \
    .format("cloudFiles") \
    .load("s3://bucket/") \
    .writeStream \
    .option("checkpointLocation", "/tmp/ckpt/files_stream") \  # ← Outro
    .start()

# Se deletar um, o outro não é afetado
```

### Inspeção de Checkpoint

```sql
-- Verificar estado do checkpoint
SELECT * FROM delta.`/tmp/ckpt/bronze_sales`._delta_log
ORDER BY modificationTime DESC
LIMIT 5;
```

---

## Kafka Integration — Padrão de Ingestão

### Consumir Tópico Kafka

```python
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka01:9092,kafka02:9092") \
    .option("subscribe", "ecommerce_events") \
    .option("startingOffsets", "latest") \
    .option("maxOffsetsPerTrigger", "100000") \
    .load()

# Dados vêm com schema: key (bytes), value (bytes), timestamp, partition, offset
parsed_df = df.select(
    col("timestamp"),
    col("partition"),
    col("offset"),
    from_json(
        col("value").cast("string"),
        "event_id STRING, user_id STRING, amount DECIMAL(10,2), event_time TIMESTAMP"
    ).alias("parsed")
).select("timestamp", "partition", "offset", "parsed.*")

query = parsed_df.writeStream \
    .format("delta") \
    .mode("append") \
    .option("checkpointLocation", "/tmp/ckpt/kafka_ecommerce") \
    .trigger(processingTime="30 seconds") \
    .start("/dbfs/user/hive/warehouse/bronze_ecommerce")
```

---

## Stream-Stream vs Stream-Static Joins

### Stream-Stream Join (Stateful)

```python
customers_stream = spark.readStream \
    .format("cloudFiles") \
    .load("s3://bucket/customers/")

orders_stream = spark.readStream \
    .format("kafka") \
    .option("subscribe", "orders") \
    .load()

# Join: ambas são streams
joined = orders_stream.join(
    customers_stream,
    on="customer_id",
    how="inner"
)

query = joined.writeStream \
    .format("delta") \
    .mode("append") \
    .option("checkpointLocation", "/tmp/ckpt/orders_customers") \
    .trigger(processingTime="10 seconds") \
    .start("/dbfs/user/hive/warehouse/silver_orders_customers")
```

**Nota:** Stream-Stream join requer state management (overhead).

### Stream-Static Join (Mais Eficiente)

```python
orders_stream = spark.readStream \
    .format("kafka") \
    .load()

# Carregar tabela estática (recarregar a cada trigger)
customers_static = spark.read.format("delta").load("/dbfs/user/hive/warehouse/dim_customers")

# Join com estática (mais rápido)
joined = orders_stream.join(
    customers_static,
    on="customer_id",
    how="left"
)
```

**Use:** Stream com tabela Gold/dimension (Silver/Gold recarregam a cada trigger).

---

## Watermarks — Processamento de Dados Atrasados

```python
# Aceitar dados até 1 hora atrasados
df = spark.readStream \
    .format("kafka") \
    .load() \
    .withWatermark("event_time", "1 hour")  # ← Window tolerance

# Agregação com watermark
windowed_agg = df \
    .groupBy(
        window("event_time", "5 minutes", "1 minute"),  # Janela deslizante
        "region"
    ) \
    .agg(sum("amount").alias("total_sales")) \
    .select(
        col("window.start").alias("window_start"),
        col("window.end").alias("window_end"),
        "region",
        "total_sales"
    )

query = windowed_agg.writeStream \
    .format("delta") \
    .mode("append") \
    .option("checkpointLocation", "/tmp/ckpt/sales_windowed") \
    .trigger(processingTime="5 seconds") \
    .start("/dbfs/user/hive/warehouse/gold_sales_5min")
```

---

## Operações Stateful (Agregações com Estado)

### dropDuplicates com Watermark

```python
# Remover eventos duplicados em janela de 1 hora
deduped = df \
    .withWatermark("event_time", "1 hour") \
    .dropDuplicates(["event_id", "event_time"])
```

### groupByKey com Agregação Customizada

```python
# Estado: manter últimas 10 transações por usuário
state_df = df.groupByKey("user_id") \
    .mapGroupsWithState(...) \
    .writeStream \
    .format("delta") \
    .start()
```

---

## foreachBatch — Custom Sinks

```python
def process_batch(df, epoch_id):
    """Executado para cada microbatch"""
    print(f"Processando batch {epoch_id} com {df.count()} registros")

    # Validação customizada
    if df.count() == 0:
        print(f"Batch {epoch_id} vazio, pulando")
        return

    # Enviar para múltiplos destinos
    df.write \
        .format("delta") \
        .mode("append") \
        .save("/dbfs/user/hive/warehouse/gold_sales")

    # Notificar via webhook
    import requests
    requests.post("https://monitoring.example.com/batch",
                  json={"epoch": epoch_id, "rows": df.count()})

query = df.writeStream \
    .foreachBatch(process_batch) \
    .option("checkpointLocation", "/tmp/ckpt/custom_sink") \
    .trigger(processingTime="10 seconds") \
    .start()
```

---

## Gotchas e Boas Práticas

| Gotcha                              | Solução                                         |
|-------------------------------------|-------------------------------------------------|
| Deletar checkpoint = reprocessar tudo | Manter checkpoint.Location imutável            |
| Stream sem watermark = late data perdida | Usar withWatermark() para agregações         |
| Kafka desconecta = stream morre    | Retry automático com failureOn=DeserializeException|
| foreachBatch executado 2x em falha  | Usar idempotent writes (append mode)           |
| Schema mismatch em cloudFiles      | Usar schemaEvolutionMode=addNewColumns        |
