# Star Schema: Regras Gold Layer

Padrão dimensional para analytics. Dimensões independentes, fatos com INNER JOINs, geração sintética de tabelas de data.

---

## Regras Críticas

### 1. Dimensões (dim_*)

| Regra | Detalhe | Violação |
|-------|---------|----------|
| **NUNCA derivam de silver_*_transacional** | Entidades independentes, não cópias | ❌ `SELECT DISTINCT FROM silver_vendas` |
| **Sintéticas ou de referência** | Clientes, produtos, datas podem ser tabelas autônomas na Silver | ✓ Bronze importa `ref_clientes.csv` |
| **Sempre têm surrogate key** | BIGINT gerado via ROW_NUMBER() | ✓ `ROW_NUMBER() OVER (ORDER BY id_natural)` |
| **Única chave natural por linha** | Sem duplicatas, sem NULLs em chaves | ✓ GROUP BY id_cliente |
| **SCD Type 2 opcional** | Histórico de mudanças com _start/_end datas | Adiciona complexidade, use se necessário |

### 2. Tabela de Datas (dim_data)

| Regra | Detalhe | Exemplo |
|-------|---------|---------|
| **Gerada SINTETICAMENTE** | Via SEQUENCE() + EXPLODE, NUNCA SELECT DISTINCT | ✓ SEQUENCE(DATE '2020-01-01', DATE '2030-12-31', INTERVAL 1 DAY) |
| **Cobertura ampla** | Mínimo 10 anos para análises históricas | 2020-2030 cobre casos de uso comuns |
| **Pré-calculada** | Atributos: ano, mês, trimestre, dia semana, semana ISO | Evita cálculos repetitivos em queries |
| **CLUSTER BY (data)** | Otimização por range temporal | Acelera filtros por período |

### 3. Fatos (fact_*)

| Regra | Detalhe | Impacto |
|-------|---------|--------|
| **INNER JOIN OBRIGATÓRIO** | Com TODAS as dimensões referenciadas | Elimina NULLs de chaves estrangeiras |
| **Nunca LEFT JOIN** | Se dimensão não existe, registro deve ser rejeitado | Mantém integridade referencial |
| **Granularidade fixa** | 1 linha = 1 transação ou 1 evento | Evita ambiguidade em agregações |
| **Surrogate keys de dim_*** | FK aponta para dim_*.surrogate_key | Não para IDs naturais |
| **Métricas aditivas** | SUM, COUNT, AVG válidos; DISTINCT(id) usa GROUP BY | Valores devem ter semântica clara |

---

## Exemplo Completo: dim_cliente, dim_data, fact_vendas

### Silver (Dados de Origem)

```sql
-- Silver: cliente limpo da transação
CREATE OR REFRESH STREAMING TABLE silver_cliente
CLUSTER BY (id_cliente)
AS
SELECT DISTINCT
  CAST(id_cliente AS BIGINT) AS id_cliente,
  CAST(nome AS STRING) AS nome,
  CAST(cidade AS STRING) AS cidade,
  CAST(pais AS STRING) AS pais,
  CAST(data_criacao AS DATE) AS data_criacao
FROM stream(bronze_cliente)
WHERE id_cliente IS NOT NULL;

-- Silver: vendas com referências
CREATE OR REFRESH STREAMING TABLE silver_vendas
CLUSTER BY (id_venda, data_evento)
AS
SELECT
  CAST(id_venda AS BIGINT) AS id_venda,
  CAST(id_cliente AS BIGINT) AS id_cliente,
  CAST(id_produto AS BIGINT) AS id_produto,
  CAST(valor_total AS DECIMAL(18,2)) AS valor_total,
  CAST(qtd_itens AS INT) AS qtd_itens,
  CAST(data_evento AS DATE) AS data_evento,
  status
FROM stream(bronze_vendas)
WHERE id_venda IS NOT NULL
  AND id_cliente IS NOT NULL
  AND data_evento IS NOT NULL;

-- Silver: produto
CREATE OR REFRESH STREAMING TABLE silver_produto
CLUSTER BY (id_produto)
AS
SELECT DISTINCT
  CAST(id_produto AS BIGINT) AS id_produto,
  CAST(nome AS STRING) AS nome,
  CAST(categoria AS STRING) AS categoria,
  CAST(preco_unitario AS DECIMAL(10,2)) AS preco_unitario
FROM stream(bronze_produto)
WHERE id_produto IS NOT NULL;
```

### Gold: Dimensões

```sql
-- dim_cliente: Surrogate key BIGINT
CREATE OR REFRESH MATERIALIZED VIEW gold_dim_cliente
CLUSTER BY (surrogate_key)
AS
SELECT
  ROW_NUMBER() OVER (ORDER BY id_cliente) AS surrogate_key,
  id_cliente,
  nome,
  cidade,
  pais,
  data_criacao,
  current_timestamp() AS _created_at
FROM silver_cliente
WHERE id_cliente IS NOT NULL;

-- dim_produto: Surrogate key BIGINT
CREATE OR REFRESH MATERIALIZED VIEW gold_dim_produto
CLUSTER BY (surrogate_key)
AS
SELECT
  ROW_NUMBER() OVER (ORDER BY id_produto) AS surrogate_key,
  id_produto,
  nome,
  categoria,
  preco_unitario,
  current_timestamp() AS _created_at
FROM silver_produto
WHERE id_produto IS NOT NULL;

-- dim_data: GERADO SINTETICAMENTE via SEQUENCE + EXPLODE
-- NUNCA via SELECT DISTINCT data FROM vendas
CREATE OR REFRESH MATERIALIZED VIEW gold_dim_data
CLUSTER BY (data)
AS
SELECT
  CAST(data_seq AS DATE) AS data,
  DAYOFMONTH(data_seq) AS dia,
  MONTH(data_seq) AS mes,
  QUARTER(data_seq) AS trimestre,
  YEAR(data_seq) AS ano,
  DAYOFWEEK(data_seq) AS dia_semana,  -- 1=Sunday, 7=Saturday
  CASE WHEN DAYOFWEEK(data_seq) IN (1, 7) THEN 'Fim de semana' ELSE 'Dia útil' END AS tipo_dia,
  WEEKOFYEAR(data_seq) AS semana_iso,
  CONCAT(YEAR(data_seq), '-W', LPAD(WEEKOFYEAR(data_seq), 2, '0')) AS semana_ano
FROM (
  SELECT EXPLODE(SEQUENCE(
    DATE '2020-01-01',
    DATE '2030-12-31',
    INTERVAL 1 DAY
  )) AS data_seq
)
WHERE YEAR(data_seq) >= 2020;
```

### Gold: Fatos

```sql
-- fact_vendas: INNER JOINs obrigatórios com dim_cliente, dim_produto, dim_data
CREATE OR REFRESH MATERIALIZED VIEW gold_fact_vendas
CLUSTER BY (dim_data_key, dim_cliente_key)
AS
SELECT
  -- FKs para dimensões
  dd.surrogate_key AS dim_data_key,
  dc.surrogate_key AS dim_cliente_key,
  dp.surrogate_key AS dim_produto_key,

  -- Chave natural (opcional, para auditoria)
  v.id_venda,

  -- Métricas
  v.valor_total,
  v.qtd_itens,
  v.valor_total / NULLIF(v.qtd_itens, 0) AS valor_unitario_medio,

  -- Dimensões desnormalizadas (opcional, para query performance)
  dc.nome AS cliente_nome,
  dp.categoria AS produto_categoria,

  -- Status como dimensão
  v.status

FROM silver_vendas v
-- INNER JOINs obrigatórios
INNER JOIN gold_dim_cliente dc ON v.id_cliente = dc.id_cliente
INNER JOIN gold_dim_produto dp ON v.id_produto = dp.id_produto
INNER JOIN gold_dim_data dd ON v.data_evento = dd.data

-- Fatos vazios não devem passar (auditoria)
WHERE v.id_venda IS NOT NULL;

-- Alternativa: fact_vendas_agregado por período
CREATE OR REFRESH MATERIALIZED VIEW gold_fact_vendas_diarias
CLUSTER BY (dim_data_key, dim_cliente_key)
AS
SELECT
  dd.surrogate_key AS dim_data_key,
  dc.surrogate_key AS dim_cliente_key,
  dp.surrogate_key AS dim_produto_key,

  COUNT(DISTINCT v.id_venda) AS qtd_vendas,
  SUM(v.valor_total) AS valor_total_dia,
  SUM(v.qtd_itens) AS qtd_itens_dia,
  AVG(v.valor_total) AS valor_medio_venda

FROM silver_vendas v
INNER JOIN gold_dim_cliente dc ON v.id_cliente = dc.id_cliente
INNER JOIN gold_dim_produto dp ON v.id_produto = dp.id_produto
INNER JOIN gold_dim_data dd ON v.data_evento = dd.data

GROUP BY dd.surrogate_key, dc.surrogate_key, dp.surrogate_key;
```

---

## DAG de Dependências Recomendado

```
silver_cliente
     ↓
gold_dim_cliente ──┐
                   ├→ gold_fact_vendas ← gold_dim_data
silver_produto     ├→ gold_fact_vendas_diarias
     ↓             │
gold_dim_produto ──┘

silver_vendas ─────→ gold_fact_vendas
                    gold_fact_vendas_diarias
```

**Princípio:** Nunca dim_* depende diretamente de silver_*_transacional. Sempre uma entidade de referência.

---

## Validações Obrigatórias

### Pré-Gold (Silver)

```sql
-- Verificar integridade referencial antes do join
SELECT COUNT(*)
FROM silver_vendas v
LEFT JOIN silver_cliente c ON v.id_cliente = c.id_cliente
WHERE c.id_cliente IS NULL;  -- Deve ser 0

SELECT COUNT(DISTINCT id_cliente) FROM silver_cliente;  -- Sem NULLs
```

### Pós-Gold (Fatos)

```sql
-- Validar que INNER JOINs não perderam dados
SELECT COUNT(*) FROM gold_fact_vendas;  -- Comparar com silver_vendas COUNT

-- Verificar nenhuma FK é NULL
SELECT COUNT(*) FROM gold_fact_vendas WHERE dim_cliente_key IS NULL;  -- Deve ser 0
SELECT COUNT(*) FROM gold_fact_vendas WHERE dim_data_key IS NULL;  -- Deve ser 0

-- Dim_data cobertura
SELECT MIN(data), MAX(data) FROM gold_dim_data;  -- 2020-01-01 ... 2030-12-31
```

---

## Checklist de Implementação

- [ ] dim_* não são SELECT DISTINCT de transacional
- [ ] dim_data gerada via SEQUENCE() + EXPLODE com cobertura 2020-2030
- [ ] Todos os dim_* têm surrogate_key BIGINT via ROW_NUMBER()
- [ ] fact_* usa INNER JOIN com todas as dimensões
- [ ] fact_* NUNCA tem NULLs em FK de dimensões
- [ ] Granularidade de fact definida (1 linha = ?)
- [ ] Métricas aditivas documentadas
- [ ] CLUSTER BY em todos os dim_* e fact_*
- [ ] DAG de dependências respeitado
- [ ] Validações de integridade referencial passam
