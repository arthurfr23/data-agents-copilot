# Metric Views — Databricks Metric Views (Camada Semântica)

**Último update:** 2026-04-09
**Domínio:** Metric Views, camada semântica Databricks, Genie
**Plataforma:** Databricks

---

## O Que São Metric Views?

Metric Views são camada semântica **nativa do Databricks** sobre tabelas Gold.

```
┌──────────────────────┐
│  Genie AI (Chat BI)  │
│  AI/BI Dashboards    │
│  Tools Externos      │
└──────────┬───────────┘
           │
    ┌──────▼─────────┐
    │  Metric Views  │  ← Definição de métricas
    │  (Semântica)   │
    └──────┬─────────┘
           │
    ┌──────▼────────────┐
    │  Gold Tables      │  ← Dados (fact_, dim_)
    │  (Lakehouse)      │
    └───────────────────┘
```

---

## CREATE METRIC VIEW — Sintaxe

### Exemplo: Métrica de Vendas

```sql
-- Criar métrica sobre tabela Gold
CREATE METRIC VIEW gold_catalog.sales.metrics_vendas
AS
SELECT
  data,
  regiao,
  SUM(valor) AS total_vendas,
  COUNT(*) AS num_transacoes,
  AVG(valor) AS venda_media
FROM gold_catalog.sales.fact_vendas
GROUP BY data, regiao;
```

### Estrutura Completa

```sql
CREATE METRIC VIEW schema.metric_name
OWNER = group_name  -- Proprietário (group Databricks)
COMMENT = 'Descrição'
CLUSTER BY (coluna1, coluna2)
AS
SELECT ...;
```

---

## COMMENT — Documentação de Métricas

### Padrão: Documentar com Unidade

```sql
CREATE METRIC VIEW gold_catalog.sales.metrics_vendas AS
SELECT
  data,
  regiao,
  SUM(valor) AS total_vendas
    COMMENT 'Soma das vendas em reais (R$) | Unit: BRL | Frequency: Daily',

  COUNT(*) AS num_transacoes
    COMMENT 'Contagem de transações | Unit: Count | Frequency: Daily',

  AVG(valor) AS venda_media
    COMMENT 'Valor médio por venda em reais (R$) | Unit: BRL | Frequency: Daily'
FROM gold_catalog.sales.fact_vendas
GROUP BY data, regiao
COMMENT 'Métricas de vendas diárias por região | Owner: Sales Analytics Team | Refresh: Daily 01:00 UTC';
```

### Campos Recomendados em COMMENT

| Campo         | Exemplo                      | Uso                        |
|---------------|------------------------------|---------------------------|
| Unit          | `Unit: BRL`, `Unit: Count`  | Para formatação e BI       |
| Frequency     | `Frequency: Daily`          | SLA de atualização         |
| Owner         | `Owner: Sales Team`         | Contato responsável        |
| Refresh time  | `Refresh: 01:00 UTC`        | Hora atualização           |
| Calculation   | `Calculation: SUM(...)`     | Definição clara            |

---

## CLUSTER BY — Otimizar Leitura

### Padrão: Cluster por Dimensões Comuns

```sql
CREATE METRIC VIEW gold_catalog.sales.metrics_vendas
CLUSTER BY (data, regiao) AS  -- ← Cluster otimiza filtros por data/região
SELECT
  data,
  regiao,
  SUM(valor) AS total_vendas,
  COUNT(*) AS num_transacoes
FROM gold_catalog.sales.fact_vendas
GROUP BY data, regiao;
```

**Benefício:** Queries filtrando por data/região têm data skipping automático.

---

## Casos de Uso

### 1. Métricas de Negócio (Fonte Única)

```sql
-- Métrica crítica = única fonte de verdade para KPI
CREATE METRIC VIEW gold_catalog.sales.metrics_kpi AS
SELECT
  DATE(data_venda) AS data,
  SUM(valor_liquido) AS revenue
    COMMENT 'Total receita | Unit: USD | Frequency: Real-time',

  COUNT(DISTINCT id_cliente) AS unique_customers
    COMMENT 'Clientes únicos | Unit: Count',

  DIVIDE(SUM(valor_liquido), COUNT(DISTINCT id_cliente), 0) AS arpu
    COMMENT 'Average Revenue Per User | Unit: USD'
FROM gold_catalog.sales.fact_vendas
GROUP BY DATE(data_venda);
```

**Usado por:**
- Genie (Conversational BI): "What is our revenue today?"
- AI/BI Dashboard: KPI cards, trend charts
- External tools (Tableau, Looker)

### 2. Métrica Multi-Dimensional

```sql
-- Métricas com múltiplas dimensões
CREATE METRIC VIEW gold_catalog.sales.metrics_customer_analysis AS
SELECT
  c.segmento,
  c.regiao,
  p.categoria,
  DATE(f.data_venda) AS data,

  SUM(f.valor_liquido) AS total_vendas,
  AVG(f.valor_liquido) AS avg_sale_value,
  COUNT(f.id_fato) AS transaction_count,
  COUNT(DISTINCT f.id_cliente) AS unique_customers

FROM gold_catalog.sales.fact_vendas f
INNER JOIN gold_catalog.sales.dim_cliente c ON f.sk_cliente = c.sk_cliente
INNER JOIN gold_catalog.sales.dim_produto p ON f.sk_produto = p.sk_produto
GROUP BY c.segmento, c.regiao, p.categoria, DATE(f.data_venda);
```

---

## Integração com Genie (Conversational BI)

### O Que é Genie?

Genie é ferramenta de BI conversacional (chat) no Databricks.

```
Usuário: "Show me revenue by region this month"
          ↓ (Genie compreende)
Genie: Consulta metric_views.metrics_vendas
       ├─ Filtra data >= CURRENT_DATE() - 30
       ├─ Agrupa por regiao
       └─ Retorna resultado + visualização automática
```

### Metric View Precisa para Genie Funcionar

```sql
-- Metric view SIMPLES (Genie consegue entender)
CREATE METRIC VIEW metrics_simple AS
SELECT
  data,
  regiao,
  SUM(valor) AS revenue,
  COUNT(*) AS transactions
FROM fact_vendas
GROUP BY data, regiao;

-- Genie consegue consultar:
-- "What is revenue by region?"
-- "Show transactions over time"
```

---

## AI/BI Dashboard — Widgets Automáticos

### Conectar Metric View a Dashboard

```sql
-- Em Databricks Dashboard:
-- 1. New Widget → Query
-- 2. SELECT * FROM gold_catalog.sales.metrics_vendas
-- 3. Visualizar automático (KPI card, chart)
```

### Widget Types

| Widget         | Melhor Para                   | Exemplo                    |
|----------------|-------------------------------|---------------------------|
| **Counter**    | Métrica única (KPI)           | Total Revenue, User Count  |
| **Bar Chart**  | Comparação entre categorias   | Revenue by Region          |
| **Line Chart**  | Série temporal                | Revenue over time          |
| **Scatter**    | Correlação 2D                 | Price vs Margin            |
| **Table**      | Detalhes granulares           | Top 10 customers           |

---

## Governance via Unity Catalog

### Permissões em Metric View

```sql
-- Dar acesso de leitura a grupo
GRANT SELECT ON METRIC VIEW gold_catalog.sales.metrics_vendas
  TO GROUP 'analysts@empresa.com.br';

-- Só data owners podem modificar
GRANT MODIFY ON METRIC VIEW gold_catalog.sales.metrics_vendas
  TO GROUP 'data-owners@empresa.com.br';
```

### Classificação via TBLPROPERTIES

```sql
CREATE METRIC VIEW gold_catalog.sales.metrics_vendas
AS SELECT ...
TBLPROPERTIES (
  'classification' = 'Confidencial',
  'owner' = 'sales-analytics@empresa.com.br',
  'sla_refresh' = '01:00 UTC',
  'lineage_source' = 'fact_vendas, dim_cliente, dim_produto'
);
```

---

## Performance — Opções de Refreshing

### 1. Real-time (Direto de fact_)

```sql
-- Metric view sem agregação extra (query fact_ diretamente)
CREATE METRIC VIEW metrics_realtime AS
SELECT * FROM gold_catalog.sales.fact_vendas
WHERE data_venda >= CURRENT_DATE() - 7;
-- Sempre lê dados atuais (sem cache)
```

**Vantagem:** Sempre atualizado.
**Desvantagem:** Mais lento (sem pré-agregação).

### 2. Pre-aggregated (Tabela Materializada)

```sql
-- Criar tabela pré-agregada (MATERIALIZED VIEW)
CREATE MATERIALIZED VIEW gold_catalog.sales.metrics_agg AS
SELECT
  DATE(data_venda) AS data,
  regiao,
  SUM(valor) AS total_vendas,
  COUNT(*) AS num_transacoes
FROM gold_catalog.sales.fact_vendas
GROUP BY DATE(data_venda), regiao;

-- Metric view sobre pré-agregado
CREATE METRIC VIEW metrics_fast AS
SELECT * FROM gold_catalog.sales.metrics_agg;
```

**Vantagem:** Rápido (pré-computado).
**Desvantagem:** Latência de refresh.

---

## Integração com Power BI (Fabric)

### Conectar Metric View a Power BI

```powerquery
// Em Power BI (Fabric)
let
  Source = Sql.Database("databricks-connection"),
  MetricView = Source{[Item="metrics_vendas"]}
in
  MetricView
```

**Nota:** Metric Views aparecem como tabelas normais em Power BI.

---

## Exemplo Completo — Métrica de E-Commerce

```sql
-- Métrica consolidada de e-commerce
CREATE METRIC VIEW gold_catalog.ecommerce.metrics_orders
OWNER = GROUP 'ecom-analysts'
CLUSTER BY (order_date, product_category)
AS
SELECT
  DATE(o.order_date) AS order_date,
  p.category AS product_category,
  c.segmento AS customer_segment,

  -- Medidas
  COUNT(DISTINCT o.order_id) AS total_orders
    COMMENT 'Number of orders | Unit: Count | Frequency: Real-time',

  SUM(o.order_value) AS total_revenue
    COMMENT 'Sum of order values in USD | Unit: USD | Frequency: Real-time',

  AVG(o.order_value) AS avg_order_value
    COMMENT 'Average order value in USD | Unit: USD',

  COUNT(DISTINCT o.customer_id) AS unique_customers
    COMMENT 'Unique customers | Unit: Count',

  SUM(CASE WHEN o.status = 'completed' THEN o.order_value ELSE 0 END) AS completed_revenue
    COMMENT 'Revenue from completed orders | Unit: USD'

FROM gold_catalog.ecommerce.fact_orders o
INNER JOIN gold_catalog.ecommerce.dim_product p
  ON o.product_id = p.product_id
INNER JOIN gold_catalog.ecommerce.dim_customer c
  ON o.customer_id = c.customer_id

GROUP BY DATE(o.order_date), p.category, c.segmento

COMMENT 'E-commerce order metrics | Owner: Ecommerce Analytics | Refresh: Every 1 hour | SLA: 99.9%';
```

---

## Gotchas

| Gotcha                              | Solução                                       |
|-------------------------------------|--------------------------------------------|
| Metric View sem COMMENT             | Sempre documentar unidade, frequência       |
| Sem CLUSTER BY = performance pobre | CLUSTER BY colunas de filtro comum         |
| Mudança em metric afeta Genie       | Testar em sandbox antes de atualizar       |
| Permissão por VIEW não GRANT SELECT | Usar GRANT no VIEW, não em tabelas base    |
| Query lenta em Metric View          | Usar MATERIALIZED VIEW para pre-agregação  |
