# Direct Lake Optimization — Otimização para Direct Lake

**Último update:** 2026-04-09
**Domínio:** Direct Lake, V-Order, cardinality, performance
**Plataformas:** Azure Fabric (Power BI + Direct Lake)

---

## Direct Lake — O Que É?

Direct Lake é modo de conexão sem importação de dados:

```
Power BI (Report Layer) → Direct Lake → Fabric Lakehouse (Gold Tables)
```

**vs Import Mode:**

```
Gold Tables → Import → Analysis Services Cube → Power BI
(Cópia em memória)
```

**Vantagem:** Dados sempre atualizados, sem latência de importação (< 1s).

---

## V-Order — Obrigatório para Direct Lake

### O Que É V-Order?

V-Order é formato de armazenamento otimizado para Parquet (Fabric).

```
┌─────────────────────────┐
│ Tabela Delta (sem V-Order) │
│ - Performance em queries: OK │
│ - Direct Lake performance: LENTO │
└─────────────────────────┘

┌─────────────────────────┐
│ Tabela Delta (com V-Order) │
│ - Performance em queries: OK │
│ - Direct Lake performance: RÁPIDO (10-100x) │
└─────────────────────────┘
```

### Ativar V-Order

#### Ao Criar Tabela

```sql
-- SQL Warehouse (T-SQL)
CREATE TABLE gold_vendas (
  id BIGINT,
  cliente_id BIGINT,
  data DATE,
  valor DECIMAL(10, 2)
)
WITH (
  DISTRIBUTION = HASH(id),
  ORDER (data, cliente_id)  -- V-Order
);
```

#### Em Spark (Databricks)

```python
spark.conf.set("spark.sql.parquet.vorder.enabled", "true")

df.write \
    .format("delta") \
    .mode("overwrite") \
    .option("vorder.enabled", "true") \
    .save("/dbfs/user/hive/warehouse/gold_vendas")
```

#### Verificar V-Order Habilitado

```sql
-- Verificar configuração
SELECT
  table_name,
  table_properties
FROM sys.tables
WHERE vorder_enabled = TRUE;
```

---

## CLUSTER BY — Crucial para Direct Lake

### Padrão: Cluster por Colunas de Filtro

```sql
CREATE TABLE gold_catalog.sales.fact_vendas (
  id_fato BIGINT,
  sk_cliente BIGINT,
  sk_produto BIGINT,
  sk_data BIGINT,
  valor DECIMAL(10, 2)
)
USING DELTA
CLUSTER BY (sk_data, sk_cliente)  -- ← CRÍTICO para Direct Lake
TBLPROPERTIES (
  'delta.enableColumnMapping' = 'true',
  'delta.columnMapping.mode' = 'name'
);
```

**Prioridade:**
1. **sk_data** — Coluna mais frequentemente filtrada (datas)
2. **sk_cliente** — Segunda coluna (clientes importantes)

### Impact na Performance

| Sem CLUSTER BY | Com CLUSTER BY |
|----------------|----------------|
| Query: 10s     | Query: 100ms   |
| Direct Lake: LENTO | Direct Lake: RÁPIDO |
| Data skipping: ❌ | Data skipping: ✅ |

---

## Column Type Optimization

### DATE vs TIMESTAMP

```sql
-- ❌ ERRADO: TIMESTAMP (maior tamanho)
CREATE TABLE gold_vendas (
  data_venda TIMESTAMP,  -- 8 bytes
  ...
);

-- ✅ CORRETO: DATE (menor tamanho)
CREATE TABLE gold_vendas (
  data_venda DATE,  -- 4 bytes
  ...
);
```

**Razão:** Direct Lake otimiza com DATE para séries temporais.

### BIGINT para Chaves

```sql
-- ✅ SEMPRE BIGINT para FK
CREATE TABLE gold_vendas (
  sk_cliente BIGINT,    -- 8 bytes (seguro para milhões)
  sk_produto BIGINT,
  ...
);

-- ❌ NUNCA INT para FK (risco overflow)
-- INT max = 2.1 bilhões (pode não ser suficiente)
```

### String Cardinality

```sql
-- ✅ Baixa cardinalidade: OK usar STRING
CREATE TABLE gold_clientes (
  segmento VARCHAR(20),  -- 'Premium', 'Gold', 'Silver', 'Bronze' (4 valores)
  ...
);

-- ❌ Alta cardinalidade: EVITAR
-- UUID BIGINT seria melhor
CREATE TABLE gold_clientes (
  uuid_cliente VARCHAR(36),  -- 36 caracteres x 10M = 360MB+ (ineficiente)
  ...
);
```

---

## Cardinality Limits — Evitar Alto Número de Distintos

### Padrão Seguro

| Coluna             | Cardinality | Recomendação            |
|--------------------|-------------|------------------------|
| Data               | 10K         | ✅ OK (10 anos de dados) |
| Cliente            | 1-10M       | ✅ OK (FK integer)      |
| Região             | 27          | ✅ OK (27 UFs)          |
| Email              | 10M         | ⚠️ CUIDADO (se exposto)  |
| UUID               | 1B+         | ❌ EVITAR em Direct Lake|

### Reduzir Cardinality

```sql
-- ❌ ERRADO: Email direta na tabela fato
CREATE TABLE fact_vendas (
  cliente_email VARCHAR(100),  -- 10M valores distintos em Direct Lake = LENTO
  ...
);

-- ✅ CORRETO: Email na dimensão, FK na fato
CREATE TABLE dim_cliente (
  sk_cliente BIGINT,
  cliente_email VARCHAR(100),
  ...
);

CREATE TABLE fact_vendas (
  sk_cliente BIGINT,  -- 10M valores, mas índice (rápido)
  ...
);
```

---

## Framing — Relacionamentos Corretos para Direct Lake

### Many-to-One (Recomendado)

```
fact_vendas (Many) ← sk_cliente → dim_cliente (One)

Exemplo:
- fact_vendas: 1 bilhão linhas
- dim_cliente: 10 milhões
- Ratio: 100:1 (muitos para um)
```

**Performance:** Ótima no Direct Lake (índice automático).

### One-to-Many (EVITAR)

```
dim_cliente (One) → sk_cliente ← fact_vendas (Many)
```

**Problema:** Direct Lake assume cardinalidade baixa em "One" side.

---

## Calculated Columns — Evitar em Direct Lake

### ❌ ERRADO: Coluna Calculada no Direct Lake

```dax
-- Em Power BI, coluna calculada sobre Direct Lake
Profit per Unit =
  fact_vendas[valor_unitario] - fact_vendas[preco_custo]
```

**Problema:**
- Recalcula a cada query
- Sem benefício de V-Order
- Lento em Direct Lake

### ✅ CORRETO: Calcular na Gold Layer

```sql
-- No Lakehouse (Gold), criar coluna calculada
CREATE TABLE gold_vendas (
  sk_cliente BIGINT,
  valor_unitario DECIMAL(10, 2),
  preco_custo DECIMAL(10, 2),
  margem_unitaria DECIMAL(10, 2) AS (valor_unitario - preco_custo),  -- Coluna calculada na tabela
  ...
) USING DELTA;
```

**Vantagem:**
- Coluna materializada (já calcula uma vez)
- Direct Lake usa V-Order
- Power BI lê valor pré-calculado (rápido)

---

## Fallback to Import Mode — Quando Acontece?

Direct Lake pode "cair" para Import Mode (menos eficiente) se:

### Cenários de Fallback

| Cenário                          | Solução                                    |
|----------------------------------|--------------------------------------------|
| Coluna calculada no Power BI    | Mover para Gold Layer (Lakehouse)         |
| High cardinality column (> 1B)  | Usar FK (integer) ao invés de UUID/string |
| Join Many-to-Many              | Criar tabela bridge no Lakehouse          |
| Implicit measure               | Definir medida explícita em DAX            |
| Format string fora do padrão    | Simplificar formato                        |

### Verificar Mode Ativo

```powerquery
// Em Power BI Desktop
1. Home → Transform data → Query Editor
2. Ver "Connection Mode" no rodapé
3. Se "Direct Lake" (verde) = OK
4. Se "Import" (azul) = Fallback
```

---

## Performance Checklist — Direct Lake Ready

### Tabela Gold Checklist

```sql
-- Verificar V-Order
SELECT table_name, vorder_enabled
FROM sys.tables
WHERE table_name = 'fact_vendas';
-- Expected: vorder_enabled = TRUE

-- Verificar CLUSTER BY
SELECT column_name, is_clustered
FROM sys.table_columns
WHERE table_name = 'fact_vendas';
-- Expected: sk_data, sk_cliente = clustered

-- Verificar Tipos
SELECT column_name, data_type
FROM sys.columns
WHERE table_name = 'fact_vendas';
-- Expected: DATE (não TIMESTAMP), BIGINT (não UUID)

-- Verificar Cardinality
SELECT
  COUNT(DISTINCT sk_cliente) / COUNT(*) AS cardinality_ratio
FROM fact_vendas;
-- Expected: < 1.0 (mais registros que clientes)
```

### Power BI Checklist

```
☑ Semantic Model criado em Fabric
☑ Fact table referenciada via Direct Lake
☑ Relationships Many-to-One
☑ Calculated columns em DAX minimizadas
☑ Measures definidas (não implicit)
☑ Query performance < 1 segundo
☑ Connection mode = "Direct Lake" (não Import)
```

---

## Exemplo Completo: Direct Lake Ready

### 1. Gold Layer (Lakehouse)

```sql
-- V-Order + CLUSTER BY + Tipos Otimizados
CREATE TABLE gold_catalog.sales.fact_vendas (
  id_fato BIGINT,
  sk_cliente BIGINT,     -- BIGINT FK (não UUID)
  sk_produto BIGINT,
  sk_data BIGINT,
  quantidade INT,
  valor_unitario DECIMAL(10, 2),
  preco_custo DECIMAL(10, 2),
  margem_unitaria DECIMAL(10, 2) AS (valor_unitario - preco_custo),
  created_at TIMESTAMP
)
USING DELTA
CLUSTER BY (sk_data, sk_cliente)  -- V-Order + CLUSTER
TBLPROPERTIES ('classification' = 'Confidencial');
```

### 2. Semantic Model (Fabric)

```powerquery
// Conectar fact_vendas via Direct Lake
let
  Source = Sql.Database("lakehouse-connection"),
  fact_vendas = Source{[Item="fact_vendas"]}
in
  fact_vendas
```

### 3. DAX Measures

```dax
Total Sales = SUM(fact_vendas[valor_unitario] * fact_vendas[quantidade])
Total Cost = SUM(fact_vendas[preco_custo] * fact_vendas[quantidade])
Total Margin = [Total Sales] - [Total Cost]
```

---

## Gotchas

| Gotcha                              | Solução                                      |
|-------------------------------------|--------------------------------------------|
| V-Order não habilitado              | Usar `spark.sql.parquet.vorder.enabled=true` |
| Sem CLUSTER BY = performance ruim   | Sempre CLUSTER BY colunas de filtro       |
| TIMESTAMP ao invés de DATE          | Usar DATE (mais compacto)                  |
| UUID/string em FK                   | Usar BIGINT integer                        |
| Coluna calculada no Power BI        | Mover para Lakehouse (Gold layer)         |
| Fallback para Import Mode           | Verificar cardinality, joins, cálculos    |
