# Reporting Patterns — Dashboards e Relatórios

**Último update:** 2026-04-09
**Domínio:** Design de dashboards, relatórios, BI patterns
**Plataformas:** Databricks AI/BI Dashboards, Power BI Fabric

---

## AI/BI Dashboards (Databricks)

### Widgets — Tipos Disponíveis

| Widget      | Caso de Uso                           | Exemplo                    |
|-------------|---------------------------------------|---------------------------|
| **Counter** | KPI único, valor total                | Total Revenue, User Count  |
| **Gauge**   | Progresso vs meta                     | YTD vs Target (90% de 100%)|
| **Bar**     | Comparação entre categorias           | Sales by Region            |
| **Line**    | Série temporal, tendência             | Revenue trend (30 dias)    |
| **Pivot**   | Tabulação cruzada                     | Revenue x Region x Category |
| **Scatter** | Correlação 2D, bubble                 | Price vs Margin x Volume   |
| **Map**     | Geolocalização                       | Sales map by state         |
| **Table**   | Detalhes granulares                   | Top 10 customers           |

### Grid Layout — 6 Colunas

Dashboards Databricks usam grid de 6 colunas para layout responsivo.

---

## Power BI em Fabric — Direct Lake

Conexão sem importação de dados: Power BI conecta diretamente às Gold Tables do Lakehouse com latência sub-segundo.

### Recomendação: Sempre Direct Lake para Gold Tables

Usar conexão Direct Lake (não Import mode) para maximizar performance.

---

## Query em Dashboard — Field Matching Rules

Para widgets funcionarem, nomes em SQL devem match com encodings visualizados.

### Exemplo: Bar Chart

```sql
SELECT
  regiao,
  COUNT(*) AS num_vendas,
  SUM(valor) AS total_vendas
FROM fact_vendas
GROUP BY regiao;
```

Widget encoding DEVE referenciar exatos: X-axis: "regiao", Y-axis: "total_vendas", "num_vendas".

---

## Padrão: KPIs no Topo

Dashboard recomendado começa com KPIs críticos (Contadores), seguidos de trends, breakdowns e detalhes.

Hierarquia visual: Importância ↓ = Tamanho ↓

---

## Validação de Query — Antes de Deployment

### Checklist: SQL Validation

- Query retorna dados sem erros
- Sem NULL em dimensões
- Field types compatíveis (numeric Y-axis, category X-axis)
- Execution time < 5 segundos
- Dados atualizados

### Checklist: Widget Validation

- Query fields existem com nomes exatos
- Field types Match com encodings
- Sem valores inesperados
- Dashboard carrega rápido (8-10 widgets max)

---

## Design Principles

### 1. Hierarquia Visual

KPI crítico maior, secundários médios, detalhes pequenos.

### 2. Paleta de Cores

Max 5 cores: Verde (positivo), Vermelho (negativo), Cinza (neutro), Laranja (warning), Dark Red (alerta).

### 3. Filtros Cascata

Filtros ano → trimestre → região → customer (dinâmicos).

---

## Exemplo Completo — Dashboard de Vendas

```sql
SELECT
  data_venda,
  regiao,
  categoria_produto,
  SUM(valor_liquido) AS total_vendas,
  SUM(quantidade) AS total_items,
  COUNT(DISTINCT id_cliente) AS unique_customers,
  AVG(valor_liquido) AS avg_sale_value
FROM gold_catalog.sales.fact_vendas f
INNER JOIN gold_catalog.sales.dim_cliente c ON f.sk_cliente = c.sk_cliente
INNER JOIN gold_catalog.sales.dim_produto p ON f.sk_produto = p.sk_produto
WHERE data_venda >= CURRENT_DATE() - 90
GROUP BY data_venda, regiao, categoria_produto
ORDER BY data_venda DESC, regiao;
```

Dashboard structure: KPI row (4 contadores) → Trends (2 line charts) → Distribution (bar chart) → Details (pivot table).

---

## Gotchas

| Gotcha                              | Solução                                       |
|-------------------------------------|--------------------------------------------|
| Query field != Widget encoding      | Usar nomes exatos (case-sensitive)          |
| NULL em dimensões                  | WHERE column IS NOT NULL em agregação       |
| Query > 30s execution time          | Adicionar filtro temporal (últimos 90 dias) |
| Cores não contrastam                | Testar com modo alto contraste              |
| Widget sem título/legenda           | Sempre adicionar labels e tooltips          |
| Dashboard lento no carregamento     | Limitar a 8-10 widgets máximo              |
