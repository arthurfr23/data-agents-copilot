# Star Schema Rules — SQL para Modelos Dimensionais

**Último update:** 2026-04-09
**Domínio:** Star Schema SQL, dim_*, fact_*, relacionamentos
**Referência:** pipeline-design/star-schema-design.md (design alto-nível)

---

## Regra 1: Dimensões (dim_*) Nunca Derivam de Transacionais

### ❌ ERRADO: dim_* copiada de silver_*

```sql
-- ANTI-PATTERN: Copiar tabela transacional para "dimensão"
CREATE OR REPLACE TABLE gold_catalog.sales.dim_cliente AS
SELECT DISTINCT
  id_cliente,
  nome,
  email,
  endereco,
  data_cadastro
FROM silver_crm.clientes;  -- ← Cópia literal, sem tratamento
```

**Problema:**
- silver_crm.clientes muda (atualizações diárias)
- dim_cliente deve ter histórico (SCD2)
- Sem chave substituta (surrogate key)

### ✅ CORRETO: dim_* com Lógica Explícita

```sql
CREATE OR REPLACE MATERIALIZED VIEW gold_catalog.sales.dim_cliente AS
SELECT
  -- Surrogate key (não deixar exposto de ID original)
  ROW_NUMBER() OVER (ORDER BY id_cliente) AS sk_cliente,

  -- Atributos descritivos
  id_cliente AS nk_cliente,  -- Natural key (negócio)
  TRIM(nome) AS cliente_nome,  -- Limpeza
  LOWER(email) AS cliente_email,
  COALESCE(endereco, 'DESCONHECIDO') AS cliente_endereco,
  CASE
    WHEN YEAR(data_cadastro) < 2015 THEN 'Legacy'
    WHEN YEAR(data_cadastro) < 2020 THEN 'Antigo'
    ELSE 'Recente'
  END AS cohort_cliente,

  -- Controle (SCD2)
  CURRENT_DATE() AS data_inicio,
  CAST(NULL AS DATE) AS data_fim,
  TRUE AS is_ativo
FROM silver_crm.clientes
WHERE data_cadastro IS NOT NULL
  AND id_cliente > 0;
```

---

## Regra 2: dim_data — SEQUENCE + EXPLODE, Nunca SELECT DISTINCT

### ❌ ERRADO: SELECT DISTINCT de transações

```sql
-- ANTI-PATTERN: Retirar datas de transações (incompleto)
CREATE TABLE gold_catalog.shared.dim_data AS
SELECT DISTINCT data_venda AS data
FROM silver_crm.vendas
ORDER BY data_venda;
-- Resultado: Apenas datas com vendas (lacunas para fins de semana)
```

### ✅ CORRETO: SEQUENCE para Calendário Completo

```sql
CREATE TABLE gold_catalog.shared.dim_data (
  id_data BIGINT NOT NULL COMMENT 'PK',
  data DATE NOT NULL COMMENT 'Data calendário',
  ano INT COMMENT 'Ano (YYYY)',
  trimestre INT COMMENT 'Trimestre (1-4)',
  mes INT COMMENT 'Mês (1-12)',
  dia INT COMMENT 'Dia do mês (1-31)',
  dia_semana INT COMMENT 'Dia da semana (0-6, 0=Dom)',
  semana_ano INT COMMENT 'Semana do ano (1-53)',
  is_fim_semana BOOLEAN COMMENT 'True se sábado/domingo',
  is_feriado BOOLEAN COMMENT 'True se feriado BR',
  nome_feriado VARCHAR(100) COMMENT 'Qual feriado',
  data_inicio TIMESTAMP COMMENT 'SCD2 begin',
  data_fim TIMESTAMP COMMENT 'SCD2 end',
  is_ativo BOOLEAN COMMENT 'SCD2 active'
)
USING DELTA
COMMENT 'Dimensão de Data - Calendário de 2020 a 2030'
TBLPROPERTIES ('classification' = 'Público');

-- Inserir usando SEQUENCE
INSERT INTO gold_catalog.shared.dim_data
SELECT
  ROW_NUMBER() OVER (ORDER BY data) AS id_data,
  data,
  YEAR(data) AS ano,
  QUARTER(data) AS trimestre,
  MONTH(data) AS mes,
  DAY(data) AS dia,
  DAYOFWEEK(data) - 1 AS dia_semana,  -- 0=Dom
  WEEKOFYEAR(data) AS semana_ano,
  DAYOFWEEK(data) IN (1, 7) AS is_fim_semana,
  data IN ('2026-04-21', '2026-05-01', '2026-09-07', '2026-12-25') AS is_feriado,  -- Feriados BR
  CASE
    WHEN data IN ('2026-04-21', '2026-05-01', '2026-09-07', '2026-12-25')
      THEN NAME_OF_FERIADO_BR(data)
    ELSE NULL
  END AS nome_feriado,
  CURRENT_TIMESTAMP() AS data_inicio,
  CAST(NULL AS TIMESTAMP) AS data_fim,
  TRUE AS is_ativo
FROM (
  SELECT EXPLODE(SEQUENCE(
    DATE '2020-01-01',
    DATE '2030-12-31',
    INTERVAL 1 DAY
  )) AS data
);
```

---

## Regra 3: fact_* Sempre INNER JOIN com Todas as Dimensões

### ❌ ERRADO: LEFT JOIN em dimensões

```sql
-- ANTI-PATTERN: LEFT JOIN (pode gerar NULLs na chave)
CREATE MATERIALIZED VIEW gold_catalog.sales.fact_vendas AS
SELECT
  id_venda,
  c.sk_cliente,  -- ← LEFT JOIN pode gerar NULL aqui
  p.sk_produto,
  d.id_data,
  v.quantidade,
  v.valor
FROM silver_crm.vendas v
LEFT JOIN gold_catalog.sales.dim_cliente c ON v.id_cliente = c.nk_cliente
LEFT JOIN gold_catalog.sales.dim_produto p ON v.id_produto = p.nk_produto
LEFT JOIN gold_catalog.shared.dim_data d ON DATE(v.data_venda) = d.data;
```

### ✅ CORRETO: INNER JOIN (garante referência válida)

```sql
CREATE MATERIALIZED VIEW gold_catalog.sales.fact_vendas AS
SELECT
  ROW_NUMBER() OVER (ORDER BY v.id_venda) AS id_fato,

  -- Foreign keys (nunca NULL com INNER JOIN)
  c.sk_cliente,
  p.sk_produto,
  d.id_data,

  -- Degenerate dimensions (do fato)
  v.id_venda AS nk_venda,
  v.numero_nfe AS numero_nfe,

  -- Measures (agregáveis)
  v.quantidade,
  v.valor_unitario,
  v.quantidade * v.valor_unitario AS valor_bruto,
  v.desconto_pct,
  (v.quantidade * v.valor_unitario) * (1 - v.desconto_pct / 100) AS valor_liquido,

  -- Controle
  CURRENT_TIMESTAMP() AS created_at,
  CURRENT_TIMESTAMP() AS updated_at
FROM silver_crm.vendas v
INNER JOIN gold_catalog.sales.dim_cliente c
  ON v.id_cliente = c.nk_cliente
  AND c.is_ativo = TRUE  -- ← Apenas versão ativa (SCD2)
INNER JOIN gold_catalog.sales.dim_produto p
  ON v.id_produto = p.nk_produto
  AND p.is_ativo = TRUE
INNER JOIN gold_catalog.shared.dim_data d
  ON DATE(v.data_venda) = d.data
WHERE v.id_venda > 0  -- Validação de negócio
  AND v.quantidade > 0
  AND v.valor_unitario > 0;
```

---

## Regra 4: CLUSTER BY em Tabelas Gold (Nunca PARTITION BY + ZORDER)

### ❌ ERRADO: PARTITION BY em MATERIALIZED VIEW

```sql
-- ANTI-PATTERN: Particionar em view (ineficiente)
CREATE MATERIALIZED VIEW gold_catalog.sales.fact_vendas
PARTITIONED BY (data_venda) AS
SELECT ...;
```

**Problema:** MATERIALIZED VIEW não permite PARTITION BY (apenas em tabelas).

### ✅ CORRETO: CLUSTER BY

```sql
CREATE TABLE gold_catalog.sales.fact_vendas (
  id_fato BIGINT,
  data_venda DATE,
  id_cliente BIGINT,
  valor DECIMAL(10, 2),
  ...
)
USING DELTA
CLUSTER BY (data_venda, id_cliente)  -- ← Clustering duplo
COMMENT 'Fatos de Vendas'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
```

**Vantagem:** Data skipping automático em filtros `WHERE data_venda = ...`.

### Alternativa: MATERIALIZED VIEW com View Clustering

```sql
-- Em Databricks 13.1+: View clustering
CREATE MATERIALIZED VIEW gold_catalog.sales.fact_vendas AS
SELECT ... FROM silver_crm.vendas
CLUSTER BY (data_venda, id_cliente);
```

---

## Surrogate Key Generation — Chaves Únicas

### Opção 1: BIGINT com ROW_NUMBER()

```sql
SELECT
  ROW_NUMBER() OVER (ORDER BY id_cliente, data_cadastro) AS sk_cliente,
  id_cliente AS nk_cliente,
  -- Atributos...
FROM silver_crm.clientes;
```

**Vantagem:** Determinístico (mesmo resultado sempre).
**Desvantagem:** Não é ordenado por natureza de negócio.

### Opção 2: BIGINT com MONOTONICALLY_INCREASING_ID()

```python
# Python
from pyspark.sql.functions import monotonically_increasing_id

df_clientes = spark.read.format("delta").load("silver_crm/clientes")
df_with_sk = df_clientes.withColumn("sk_cliente", monotonically_increasing_id())

df_with_sk.write.format("delta").mode("overwrite").save("gold/dim_cliente")
```

**Vantagem:** Única garantia de unicidade na distribuição Spark.
**Desvantagem:** Não determinístico (valores mudam em re-run).

### Opção 3: HASH para SCD2

```sql
-- SCD2: múltiplas versões do mesmo cliente
SELECT
  CONCAT(id_cliente, '-', ROW_NUMBER() OVER (PARTITION BY id_cliente ORDER BY data_inicio)) AS sk_cliente,
  id_cliente AS nk_cliente,
  -- Atributos...
  data_inicio,
  data_fim,
  is_ativo
FROM silver_crm.clientes_hist;
```

---

## Chave de Negócio (Natural Key) vs Chave Substituta

### Chave de Negócio (nk_*)

```sql
-- Identificador único no domínio de negócio
id_cliente = 12345
id_produto = 'SKU-2024-001'
```

**Uso:** Chave estrangeira no fato (naturaleza).

### Chave Substituta (sk_*)

```sql
-- Identificador técnico para performance
sk_cliente = 1
sk_produto = 1
```

**Uso:** PK na dimensão (separar técnico de negócio).

### Padrão Recomendado

```sql
-- Dimensão tem ambas
CREATE TABLE gold_catalog.sales.dim_cliente (
  sk_cliente BIGINT PRIMARY KEY,    -- Substituta (técnica)
  nk_cliente BIGINT UNIQUE,         -- Natural (negócio)
  nome STRING,
  ...
);

-- Fato referencia apenas substituta (menor tamanho)
CREATE TABLE gold_catalog.sales.fact_vendas (
  sk_cliente BIGINT,  -- ← Referencia sk_cliente
  sk_produto BIGINT,
  ...
);

-- BI pode joinar para obter nk_ se precisar
```

---

## Slowly Changing Dimensions (SCD2) em SQL

### SCD2 Implementação Completa

```sql
-- Manter histórico de mudanças em dimensão
CREATE TABLE gold_catalog.sales.dim_cliente (
  sk_cliente BIGINT NOT NULL,
  nk_cliente BIGINT NOT NULL,
  nome STRING,
  email STRING,
  endereco STRING,
  data_inicio TIMESTAMP NOT NULL,
  data_fim TIMESTAMP,  -- NULL = versão ativa
  is_ativo BOOLEAN DEFAULT TRUE,
  versao INT DEFAULT 1
);

-- Atualizar quando cliente muda de endereço
MERGE INTO gold_catalog.sales.dim_cliente t
USING (
  SELECT
    id_cliente,
    nome,
    email,
    endereco
  FROM silver_crm.clientes
) s
  ON t.nk_cliente = s.id_cliente AND t.is_ativo = TRUE
WHEN MATCHED AND t.endereco != s.endereco THEN
  -- Fechar versão anterior
  UPDATE SET
    data_fim = CURRENT_TIMESTAMP(),
    is_ativo = FALSE
WHEN NOT MATCHED THEN
  -- Inserir cliente novo
  INSERT (sk_cliente, nk_cliente, nome, email, endereco, data_inicio, is_ativo)
  VALUES (
    ROW_NUMBER() OVER (ORDER BY s.id_cliente),
    s.id_cliente, s.nome, s.email, s.endereco,
    CURRENT_TIMESTAMP(), TRUE
  );

-- Inserir nova versão (após UPDATE)
INSERT INTO gold_catalog.sales.dim_cliente
SELECT
  ROW_NUMBER() OVER (ORDER BY s.id_cliente),
  s.id_cliente,
  s.nome,
  s.email,
  s.endereco,
  CURRENT_TIMESTAMP(),
  NULL,  -- sem data_fim (ativa)
  TRUE,
  t.versao + 1
FROM silver_crm.clientes s
JOIN gold_catalog.sales.dim_cliente t
  ON s.id_cliente = t.nk_cliente
  AND t.is_ativo = FALSE
  AND t.data_fim = CURRENT_TIMESTAMP();  -- Apenas as que fechamos
```

---

## Gotchas

| Gotcha                              | Solução                                         |
|-------------------------------------|--------------------------------------------|
| dim_* com dados transacionais       | Sempre agregado/deduplicated                |
| fact_* com LEFT JOIN na dimensão   | Usar INNER JOIN (garantir FK válida)       |
| SELECT DISTINCT para calendário    | Usar SEQUENCE + EXPLODE                     |
| PARTITION BY em MATERIALIZED VIEW  | Usar CLUSTER BY em tabelas                 |
| SCD2 sem data_fim = múltiplas ativas | Sempre um registro ativo (data_fim = NULL)|
