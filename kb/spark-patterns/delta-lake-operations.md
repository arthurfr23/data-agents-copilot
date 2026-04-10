# Delta Lake Operations — Operações Avançadas

**Último update:** 2026-04-09
**Domínio:** MERGE, OPTIMIZE, VACUUM, Time Travel, CDC
**Plataformas:** Databricks, Azure Fabric

---

## MERGE INTO — Upsert Eficiente

### Padrão Padrão: Inserir ou Atualizar

```sql
MERGE INTO gold_catalog.sales.fact_vendas AS target
USING staging.vendas_new AS source
  ON target.id_venda = source.id_venda
    AND target.data_venda = source.data_venda  -- Compound key
WHEN MATCHED AND target.valor < source.valor THEN
  UPDATE SET
    valor = source.valor,
    desconto = source.desconto,
    updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (id_venda, data_venda, valor, desconto, created_at)
  VALUES (source.id_venda, source.data_venda, source.valor, source.desconto, CURRENT_TIMESTAMP());
```

### Performance Tip: Filtrar Target Antes de MERGE

```sql
-- ❌ LENTO: MERGE varre TODA a tabela target
MERGE INTO gold_catalog.sales.fact_vendas AS target
USING staging.vendas_new AS source
  ON target.id_venda = source.id_venda
WHEN MATCHED THEN UPDATE SET valor = source.valor
WHEN NOT MATCHED THEN INSERT *;

-- ✅ RÁPIDO: Filtrar partição primeiro
MERGE INTO gold_catalog.sales.fact_vendas AS target
USING staging.vendas_new AS source
  ON target.id_venda = source.id_venda
    AND target.data_venda >= CURRENT_DATE() - 7  -- ← Filtro de partição
WHEN MATCHED THEN UPDATE SET valor = source.valor
WHEN NOT MATCHED THEN INSERT *;
```

**Por quê?** MERGE com partição ativa permite skipping de arquivos (menos I/O).

### SCD2 com MERGE

```sql
-- Slowly Changing Dimension Type 2: manter histórico
MERGE INTO gold_catalog.customers.dim_cliente AS target
USING (
  SELECT
    id_cliente,
    nome,
    email,
    endereco,
    CURRENT_TIMESTAMP() AS effective_from,
    CAST(NULL AS TIMESTAMP) AS effective_to
  FROM staging.clientes_new
) AS source
  ON target.id_cliente = source.id_cliente
    AND target.effective_to IS NULL  -- Ativa apenas
WHEN MATCHED AND target.nome != source.nome THEN
  -- Fechar registro antigo, inserir novo
  UPDATE SET effective_to = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (id_cliente, nome, email, endereco, effective_from, effective_to)
  VALUES (source.id_cliente, source.nome, source.email, source.endereco, source.effective_from, NULL);

-- Inserir nova versão (após UPDATE)
INSERT INTO gold_catalog.customers.dim_cliente
SELECT * FROM (
  SELECT
    source.id_cliente,
    source.nome,
    source.email,
    source.endereco,
    CURRENT_TIMESTAMP() AS effective_from,
    CAST(NULL AS TIMESTAMP) AS effective_to
  FROM staging.clientes_new source
  WHERE EXISTS (
    SELECT 1 FROM gold_catalog.customers.dim_cliente target
    WHERE target.id_cliente = source.id_cliente
      AND target.nome != source.nome
      AND target.effective_to IS NULL
  )
);
```

---

## OPTIMIZE — Compactar Arquivos Pequenos

### Problema: Muitos Pequenos Arquivos

```
/warehouse/gold_sales/
├─ part-00000.parquet (1MB)
├─ part-00001.parquet (1MB)
├─ part-00002.parquet (1MB)
├─ part-00003.parquet (1MB)
└─ _delta_log/
```

**Problema:** 4 arquivos de 1MB = overhead de leitura (4x operações I/O).

### Solução: OPTIMIZE com ZORDER/CLUSTER BY

```sql
-- Compactar e reordenar por colunas de filtro
OPTIMIZE gold_catalog.sales.fact_vendas
ZORDER BY (data_venda, regiao);  -- ← Prioridade de filtro
```

```sql
-- Moderno: CLUSTER BY (melhor que ZORDER)
OPTIMIZE gold_catalog.sales.fact_vendas
CLUSTER BY (data_venda, regiao);
```

**Resultado:**
```
/warehouse/gold_sales/
├─ part-00000.parquet (256MB)  # Compactado
└─ _delta_log/
```

**Vantagem:** Queries filtrando por data_venda/regiao pula arquivos irrelevantes (data skipping).

### Schedule Automático

```sql
-- Executar diariamente (jobcluster)
OPTIMIZE gold_catalog.sales.fact_vendas
CLUSTER BY (data_venda, regiao);

-- Ou em pipeline Python:
# spark.sql("OPTIMIZE gold_catalog.sales.fact_vendas CLUSTER BY (data_venda, regiao)")
```

---

## VACUUM — Limpar Arquivos Antigos

### Padrão: Manter 7 dias de histórico

```sql
-- ✅ CORRETO: Reter dados para Time Travel
VACUUM gold_catalog.sales.fact_vendas
RETAIN 168 HOURS;  -- 7 dias (default)
```

### Risco: VACUUM = Perder Time Travel

```sql
-- ❌ NUNCA: Definir retention = 0
VACUUM gold_catalog.sales.fact_vendas RETAIN 0 HOURS;
-- Resultado: Perder TODA histórico Delta (não recuperável)
```

| Retenção  | Custo Armazenamento | Time Travel | Use Case                    |
|-----------|---------------------|-------------|---------------------------|
| 0 hours   | Mínimo              | Não         | ❌ NUNCA em produção      |
| 24 hours  | Baixo               | 1 dia       | CUIDADO: pouco histórico  |
| 168 hours | Médio               | 7 dias      | ✅ Recomendado (default) |
| 720 hours | Alto                | 30 dias     | ✅ Para dados críticos    |

### Limpeza Segura: Backup Antes

```sql
-- 1. Criar backup (snapshot Time Travel)
CREATE TABLE gold_catalog.sales.fact_vendas_backup_2026_04_01 AS
SELECT * FROM gold_catalog.sales.fact_vendas;

-- 2. VACUUM com confiança
VACUUM gold_catalog.sales.fact_vendas RETAIN 168 HOURS;
```

---

## Time Travel — Regressar no Tempo

### Versão Específica (by Version)

```sql
-- Restaurar versão 42 (commit)
SELECT * FROM gold_catalog.sales.fact_vendas VERSION AS OF 42;

-- Verificar histórico de versões
SELECT * FROM DESCRIBE HISTORY gold_catalog.sales.fact_vendas
LIMIT 10;
```

### Timestamp Específico (by Timestamp)

```sql
-- Dados de 1 hora atrás
SELECT * FROM gold_catalog.sales.fact_vendas
TIMESTAMP AS OF '2026-04-09 13:00:00';

-- Dados de 3 dias atrás
SELECT * FROM gold_catalog.sales.fact_vendas
TIMESTAMP AS OF CURRENT_TIMESTAMP() - INTERVAL 3 DAY;
```

### Restaurar Tabela Inteira

```sql
-- Restore inteira de 1 semana atrás
RESTORE TABLE gold_catalog.sales.fact_vendas
TO TIMESTAMP AS OF CURRENT_TIMESTAMP() - INTERVAL 7 DAY;
```

---

## CLUSTER BY — Reordenação Moderna (Vs ZORDER)

### CLUSTER BY: Novo Padrão

```sql
-- Criar tabela com CLUSTER BY
CREATE TABLE gold_catalog.sales.fact_vendas (
  id_venda BIGINT,
  data_venda DATE,
  regiao STRING,
  valor DECIMAL(10, 2)
)
USING DELTA
CLUSTER BY (data_venda, regiao);  -- ← Auto-clustering
```

### ZORDER: Legado (Ainda Funciona)

```sql
-- Antigo: ZORDER BY durante CREATE
CREATE TABLE gold_catalog.sales.fact_vendas (...)
USING DELTA
TBLPROPERTIES ('delta.orderingBy' = 'data_venda,regiao');
```

### Comparação

| Aspecto        | CLUSTER BY          | ZORDER BY        |
|----------------|---------------------|------------------|
| Performance    | Melhor (nativo)     | Bom (legacy)     |
| Cardinality    | Sem limite          | Até 3 colunas    |
| Auto-clustering| Sim (background)    | Manual (OPTIMIZE)|
| Recomendação   | ✅ Novo padrão      | ⚠️ Legacy       |

---

## Change Data Feed (CDF) — Consumir Mudanças

### Habilitar CDF

```sql
-- Ao criar tabela
CREATE TABLE gold_catalog.sales.fact_vendas (...)
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true'  -- ← Habilitar CDF
);

-- Ou em tabela existente
ALTER TABLE gold_catalog.sales.fact_vendas
SET TBLPROPERTIES (delta.enableChangeDataFeed = 'true');
```

### Ler Changes

```sql
-- Mudanças entre versões
SELECT * FROM table_changes("gold_catalog.sales.fact_vendas", 10, 15);

-- Resultado: _change_type (insert, update_preimage, update_postimage, delete)
```

**Use para:**
- Replicar mudanças em tempo real (downstream)
- Auditar modificações (who changed what)
- CDC para data warehouse externo

---

## Schema Evolution — Adicionar/Remover Colunas

### mergeSchema: Permitir Novo Schema

```python
# Leitura com schema mismatch
df = spark.read \
    .option("mergeSchema", "true") \
    .parquet("s3://bucket/sales/2026-04-09/")

# Se 2026-04-09 tiver nova coluna (ex: discount), ela é aceita
```

### overwriteSchema: Substituir Schema Inteiro

```python
# Escrever com novo schema (cuidado!)
df.write \
    .option("overwriteSchema", "true") \
    .mode("overwrite") \
    .format("delta") \
    .save("/dbfs/user/hive/warehouse/fact_vendas")

# Schema anterior é descartado
```

**Use apenas quando:** Deletar coluna legada ou mudar tipo de dado (raro).

---

## Deletion Vectors — Soft Delete Eficiente

```sql
-- Ativar Deletion Vectors (Delta 2.0+)
ALTER TABLE gold_catalog.sales.fact_vendas
SET TBLPROPERTIES (delta.enableDeletionVectors = 'true');

-- Delete não reescreve arquivo inteiro
DELETE FROM gold_catalog.sales.fact_vendas
WHERE data_venda < '2020-01-01';  -- ← Rápido, usa deletion bitmap
```

**Vantagem:** Deletions não reescrevem arquivos (menor overhead).

---

## Liquid Clustering — Multi-Coluna Clustering

```sql
-- Cluster por múltiplas colunas sem ordem rígida
CREATE TABLE gold_catalog.sales.fact_vendas (
  id_venda BIGINT,
  data_venda DATE,
  regiao STRING,
  categoria STRING,
  valor DECIMAL(10, 2)
)
USING DELTA
CLUSTER BY (data_venda, regiao, categoria);  -- ← Liquid clustering
```

**Use quando:** Múltiplas colunas de filtro (sem ordem clara de prioridade).

---

## Gotchas

| Gotcha                              | Solução                                    |
|-------------------------------------|--------------------------------------------|
| MERGE sem filtro = full scan        | Sempre filtrar por partição                |
| VACUUM com RETAIN=0 = irreversível  | Manter default 168h ou maior               |
| ZORDER em tabela grande = lento    | Usar CLUSTER BY (mais eficiente)           |
| Time Travel não funciona pós-VACUUM | Manter RETAIN >= a window de recovery     |
| Schema evolution break queries      | Testar com mergeSchema em staging          |
