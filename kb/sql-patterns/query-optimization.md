# Query Optimization — Boas Práticas de Otimização SQL

**Último update:** 2026-04-09
**Domínio:** Otimização de queries, planos de execução, performance
**Plataformas:** Databricks SQL, Azure Synapse

---

## CTE (Common Table Expressions) — Legibilidade e Performance

### Padrão: CTE para Queries Complexas

```sql
-- ✅ CORRETO: CTE para modularizar
WITH vendas_filtradas AS (
  SELECT
    id_venda,
    id_cliente,
    valor
  FROM gold_catalog.sales.fact_vendas
  WHERE data_venda >= CURRENT_DATE() - 30
    AND valor > 100
),
clientes_premium AS (
  SELECT DISTINCT id_cliente
  FROM vendas_filtradas
  GROUP BY id_cliente
  HAVING COUNT(*) > 5
)
SELECT
  c.sk_cliente,
  c.cliente_nome,
  COUNT(v.id_venda) AS num_vendas,
  SUM(v.valor) AS valor_total
FROM gold_catalog.sales.dim_cliente c
INNER JOIN clientes_premium cp ON c.nk_cliente = cp.id_cliente
LEFT JOIN vendas_filtradas v ON c.nk_cliente = v.id_cliente
GROUP BY c.sk_cliente, c.cliente_nome
ORDER BY valor_total DESC;
```

**Benefícios:**
- Mais legível (separação de lógica)
- Catalyst otimiza melhor (pipeline de CTEs)
- Reutilização de CTEs (sem re-computation)

---

## SELECT * — Nunca em Produção

### ❌ ERRADO: SELECT *

```sql
-- Problema: Lê todas colunas, mesmo não usadas
SELECT * FROM gold_catalog.sales.fact_vendas;

-- Se tabela tem 50 colunas e você usa 5:
-- Usa 10x mais I/O, 10x mais rede, 10x mais memória
```

### ✅ CORRETO: Listar Colunas Explicitamente

```sql
-- Ler apenas 5 colunas necessárias
SELECT
  id_fato,
  sk_cliente,
  valor_liquido,
  data_venda,
  created_at
FROM gold_catalog.sales.fact_vendas
WHERE data_venda >= CURRENT_DATE() - 30;
```

**Vantagem:** 10x menos I/O (lê apenas colunas usadas).

---

## Predicate Pushdown — Filtrar Antes de Join

### ❌ ERRADO: Join Antes de Filtrar

```sql
-- 1. Join (tabelas grandes)
SELECT
  f.valor,
  c.nome,
  p.descricao
FROM fact_vendas f          -- 1GB
JOIN dim_cliente c          -- 200MB
  ON f.sk_cliente = c.sk_cliente
JOIN dim_produto p          -- 100MB
  ON f.sk_produto = p.sk_produto
WHERE f.data_venda >= CURRENT_DATE() - 7  -- ← Filtro DEPOIS (1.3GB lido)
  AND c.regiao = 'SP'
  AND p.categoria = 'Eletrônicos';
```

**Problema:** Join processa 1.3GB, depois filtra para 100MB.

### ✅ CORRETO: Filtrar Antes de Join

```sql
-- 1. Filtrar (reduzir tamanho primeiro)
WITH fact_recente AS (
  SELECT sk_cliente, sk_produto, valor
  FROM fact_vendas
  WHERE data_venda >= CURRENT_DATE() - 7  -- ← Filtra cedo (reduz 1GB → 50MB)
),
cliente_sp AS (
  SELECT sk_cliente, nome
  FROM dim_cliente
  WHERE regiao = 'SP'
),
produto_eletro AS (
  SELECT sk_produto, descricao
  FROM dim_produto
  WHERE categoria = 'Eletrônicos'
)
-- 2. Join (tabelas pequenas)
SELECT
  f.valor,
  c.nome,
  p.descricao
FROM fact_recente f
INNER JOIN cliente_sp c ON f.sk_cliente = c.sk_cliente
INNER JOIN produto_eletro p ON f.sk_produto = p.sk_produto;
```

**Vantagem:** Join em 50MB ao invés de 1.3GB (26x mais rápido).

---

## CLUSTER BY vs ZORDER BY

### CLUSTER BY: Novo Padrão (Recomendado)

```sql
-- Moderno: CLUSTER BY para data skipping
SELECT COUNT(*) FROM gold_catalog.sales.fact_vendas
WHERE data_venda = '2026-04-09';  -- ← Data skipping automático

-- Tabela usa: CLUSTER BY (data_venda, sk_cliente)
-- Spark pula arquivos não-relevantes (< 1 segundo)
```

### ZORDER BY: Legado

```sql
-- Antigo: ZORDER BY (menos eficiente)
OPTIMIZE gold_catalog.sales.fact_vendas
ZORDER BY (data_venda, sk_cliente);

-- Funciona, mas CLUSTER BY é melhor
```

**Comparação:**

| Aspecto         | CLUSTER BY      | ZORDER BY         |
|-----------------|-----------------|-------------------|
| Performance     | Melhor          | Bom               |
| Manutenção      | Automático      | Manual (OPTIMIZE) |
| Cardinality     | Sem limite      | Até 3 colunas     |
| Recomendação    | ✅ Usar sempre  | ⚠️ Legacy        |

---

## EXPLAIN — Analisar Plano de Execução

### Executar EXPLAIN

```sql
EXPLAIN SELECT
  c.nome,
  COUNT(f.id_fato) AS num_vendas
FROM gold_catalog.sales.dim_cliente c
LEFT JOIN gold_catalog.sales.fact_vendas f
  ON c.sk_cliente = f.sk_cliente
GROUP BY c.nome;
```

**Output (Ejemplo):**
```
== Parsed Logical Plan ==
'Aggregate ['name], [...]

== Analyzed Logical Plan ==
'Aggregate ['name], [...]

== Optimized Logical Plan ==
Aggregate [name#1], [count(...) AS count#5]
+- Join LeftOuter, (sk_cliente#2 = sk_cliente#10)
   :- Scan gold_catalog.sales.dim_cliente
   +- Scan gold_catalog.sales.fact_vendas (data_venda >= 2026-04-01) ← Predicate pushdown OK

== Physical Plan ==
SortAggregate
+- Sort
   +- Exchange hashpartitioning
      +- SortAggregate
         +- Sort
            +- BroadcastHashJoin
               :- BroadcastExchange
               |  +- Scan gold_catalog.sales.dim_cliente
               +- Scan gold_catalog.sales.fact_vendas
```

### Leitura de Plano

| Operação            | Significado                             |
|---------------------|----------------------------------------|
| Scan (partitions=5) | Lê 5 partições (bom paralelismo)       |
| BroadcastHashJoin   | Broadcast uma tabela pequena (rápido) |
| SortMergeJoin       | Sort-merge join (ambas ordenadas)     |
| ShuffleExchange     | Shuffle (alto overhead)                |

---

## Partition Pruning — Filtrar por Coluna Particionada

### Com Partição (Rápido)

```sql
-- Tabela particionada por data_venda
SELECT COUNT(*) FROM gold_catalog.sales.fact_vendas
WHERE data_venda = '2026-04-09';  -- ← Lê partição 2026-04-09 apenas
-- Tempo: 100ms (1 partição)
```

### Sem Partição Eficiente (Lento)

```sql
-- Sem partição útil, full scan
SELECT COUNT(*) FROM gold_catalog.sales.fact_vendas
WHERE sk_cliente = 123;  -- ← Full scan (todas partições)
-- Tempo: 10s (1000 partições)
```

**Otimização:** Usar CLUSTER BY ao invés de PARTITION BY (melhor que particionar).

---

## Semi-Joins vs Regular Joins

### IN / EXISTS (Semi-Join, Mais Rápido)

```sql
-- ✅ Semi-join: teste de existência
SELECT id_cliente, nome
FROM gold_catalog.sales.dim_cliente c
WHERE EXISTS (
  SELECT 1 FROM gold_catalog.sales.fact_vendas f
  WHERE f.sk_cliente = c.sk_cliente
    AND f.valor > 1000
);

-- Equivalente com IN
SELECT id_cliente, nome
FROM gold_catalog.sales.dim_cliente c
WHERE id_cliente IN (
  SELECT DISTINCT sk_cliente FROM gold_catalog.sales.fact_vendas
  WHERE valor > 1000
);
```

**Vantagem:** Semi-join retorna cliente 1x (mesmo se 10 vendas).

### Regular Join (Retorna Todas as Linhas)

```sql
-- ❌ Regular join: retorna múltiplas linhas
SELECT DISTINCT c.id_cliente, c.nome
FROM gold_catalog.sales.dim_cliente c
INNER JOIN gold_catalog.sales.fact_vendas f
  ON c.sk_cliente = f.sk_cliente
WHERE f.valor > 1000;

-- Problema: se cliente tem 10 vendas > 1000, retorna 10 linhas
-- Precisa DISTINCT para remover duplicatas (overhead)
```

**Recomendação:** Usar EXISTS/IN quando só precisa teste de existência.

---

## Aggregate Pushdown — Agregação Antes de Join

### ❌ ERRADO: Agregar Depois de Join

```sql
-- Problema: join traz dados duplicados, depois agrupa
SELECT
  c.nome,
  COUNT(f.id_fato) AS num_vendas
FROM dim_cliente c
JOIN fact_vendas f ON c.sk_cliente = f.sk_cliente  -- ← Sem filtro
GROUP BY c.nome;
```

### ✅ CORRETO: Agregar Antes (se possível)

```sql
-- Agregar fact primeiro, depois join
WITH vendas_por_cliente AS (
  SELECT
    sk_cliente,
    COUNT(*) AS num_vendas
  FROM fact_vendas
  GROUP BY sk_cliente
)
SELECT
  c.nome,
  vc.num_vendas
FROM dim_cliente c
LEFT JOIN vendas_por_cliente vc ON c.sk_cliente = vc.sk_cliente;
```

**Vantagem:** Reduz tamanho do join (1M clientes x 10M vendas → 1M clientes x 1M aggs).

---

## TABLESAMPLE — Exploração Rápida

```sql
-- Explorar tabela grande com amostra 1%
SELECT * FROM gold_catalog.sales.fact_vendas TABLESAMPLE (1 PERCENT);

-- Fixar seed para reprodutibilidade
SELECT * FROM gold_catalog.sales.fact_vendas TABLESAMPLE (1 PERCENT) REPEATABLE (42);

-- Resultado: ~1% das linhas, tempo << 1s
```

**Use para:**
- Verificar rápido estrutura de tabela
- Testar query em dados reais (sem full scan)
- Estatísticas aproximadas

---

## ANALYZE TABLE — Coletar Estatísticas

```sql
-- Coletar estatísticas para planner
ANALYZE TABLE gold_catalog.sales.fact_vendas COMPUTE STATISTICS;

-- Ver estatísticas
DESC FORMATTED gold_catalog.sales.fact_vendas;
```

**Output:**
```
# Statistics
Num Files: 256
Num Rows: 10000000
Total Size: 5.2 GB
```

**Benefício:** Planner usa estatísticas para decisões de join strategy.

---

## Gotchas

| Gotcha                              | Solução                                       |
|-------------------------------------|--------------------------------------------|
| SELECT * é mais lento               | Listar colunas explicitamente               |
| Join sem filtro = full shuffle      | Filtrar antes de join                       |
| ZORDER menos eficiente que CLUSTER  | Usar CLUSTER BY                             |
| EXPLAIN mostra lógica, não real    | Usar Query Profile para stats reais        |
| Partition pruning não funciona      | Verificar que coluna está particionada      |
| EXISTS vs IN performance = igual    | Usar EXISTS (mais legível)                  |
