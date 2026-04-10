# Lineage Documentation — Rastreamento de Linhagem de Dados

**Último update:** 2026-04-09
**Domínio:** Linhagem, rastreabilidade e impacto de mudanças
**Plataformas:** Databricks, Azure Fabric

---

## Databricks — System Tables (system.lineage)

### Tabela system.lineage.table_lineage

Registra toda transformação entre tabelas (Bronze → Silver → Gold).

```sql
-- Consultar linhagem de uma tabela Gold
SELECT
  source_table,
  target_table,
  event_time,
  query_id
FROM system.lineage.table_lineage
WHERE target_table = 'gold_catalog.sales.fact_vendas'
  AND event_date >= CURRENT_DATE() - 30
ORDER BY event_time DESC;
```

### Resultado Esperado

| source_table                  | target_table                       | event_time          | query_id |
|-------------------------------|-------------------------------------|---------------------|----------|
| silver_crm.customers          | gold_catalog.sales.dim_cliente     | 2026-04-09 10:30:00 | q-12345  |
| silver_crm.transactions       | gold_catalog.sales.fact_vendas     | 2026-04-09 10:35:00 | q-12346  |
| silver_products               | gold_catalog.sales.dim_produto     | 2026-04-09 10:40:00 | q-12347  |

### Arvore de Linhagem Completa

```sql
-- Rastrear origem até Bronze
WITH lineage_chain AS (
  SELECT
    source_table,
    target_table,
    1 AS depth,
    source_table AS origin
  FROM system.lineage.table_lineage
  WHERE target_table = 'gold_catalog.sales.fact_vendas'

  UNION ALL

  SELECT
    lc.source_table,
    tl.target_table,
    lc.depth + 1,
    lc.origin
  FROM lineage_chain lc
  JOIN system.lineage.table_lineage tl
    ON lc.source_table = tl.target_table
  WHERE lc.depth < 5  -- Evitar loops infinitos
)
SELECT * FROM lineage_chain
ORDER BY depth DESC;
```

---

## Azure Fabric — Lineage Query

### mcp__fabric_community__get_lineage

Consulta dependências upstream/downstream no Fabric.

```python
# Exemplo: obter linhagem de um Report
lineage = get_lineage(
  item_id='report-uuid',
  item_type='Report',
  direction='upstream'  # upstream=fontes, downstream=consumidores
)

# Resultado: lista de dependências
for dependency in lineage['dependencies']:
    print(f"{dependency['name']} ({dependency['type']})")
```

### mcp__fabric_community__get_dependencies

Alternativa para análise de impacto.

```python
# Quais relatórios serão impactados se eu mudar dim_cliente?
deps = get_dependencies(
  item_id='dim-cliente-uuid',
  item_type='Table'
)

# Resultado: relatórios, datasets, dataflows que consomem dim_cliente
for dependent in deps['dependents']:
    print(f"IMPACTADO: {dependent['name']} (tipo: {dependent['type']})")
```

---

## Cross-Platform — Documentação de Shortcuts e Mirroring

### Shortcuts (Fabric → Databricks)

```
bronze_catalog.logs
    ↓
SHORTCUT → /mnt/logs/parquet/
    ↓
silver_fabric.logs_processed
    ↓
gold_fabric.fact_events
```

**Documentar:**
```markdown
# Lineage: fact_events

- **Bronze (Databricks):** bronze_catalog.logs
- **Silver (Fabric):** silver_fabric.logs_processed (via SHORTCUT)
- **Gold (Fabric):** gold_fabric.fact_events

**Latência:** Shortcut atualiza a cada 5 min (arquivo-based)
**Última atualização:** 2026-04-09 14:30:00
```

### Mirroring (Fabric ↔ Fabric)

```sql
-- Fabric Workspace A: tabela spiegata
CREATE MIRRORED TABLE silver_a.customers AS
MIRROR FROM workspace_b/silver_b/customers;

-- Documentar:
-- Origem: workspace_b.silver_b.customers
-- Destino: workspace_a.silver_a.customers
-- Sincronização: contínua (latência < 1 min)
```

---

## Regra: Toda Tabela Gold Deve Ter Linhagem Documentada

### Template de Documentação

Criar arquivo `LINEAGE.md` no repositório Git próximo ao pipeline:

```markdown
# Lineage: fact_vendas

## Origem (Bronze)
- **Fonte de Dados:** SAP ERP System
- **Tabela Bronze:** bronze_catalog.erp_sales_raw
- **Frequência:** Diária (00:00 UTC)
- **Registros:** ~500k/dia

## Transformação (Silver)
- **Tabela Silver:** silver_crm.vendas_normalized
- **Lógica:** Deduplicação, validação de CPF/CNPJ, conversão de moeda
- **Frequência:** Diária (00:30 UTC)
- **Registros:** ~450k/dia (95% de retenção)

## Agregação (Gold)
- **Tabela Gold:** gold_catalog.sales.fact_vendas
- **Dimensões:** dim_cliente, dim_produto, dim_data, dim_regiao
- **Medidas:** valor_total, quantidade, desconto
- **Frequência:** Diária (01:00 UTC)
- **Granularidade:** 1 linha por transação

## Consumidores
- Dashboard "Vendas Diárias" (Power BI)
- Report "Análise de Regiões" (AI/BI Dashboard)
- Export "SAP Reconciliation" (Data Lake)

## Contatos
- **Data Owner:** datasales@empresa.com.br
- **Pipeline Owner:** dataeng@empresa.com.br
```

---

## Exemplo: Consulta Completa de Linhagem

```sql
-- Rastrear impacto: se bronze_catalog.customers mudar, o que é afetado?

WITH lineage_tree AS (
  SELECT
    source_table,
    target_table,
    event_time,
    1 AS depth
  FROM system.lineage.table_lineage
  WHERE source_table = 'bronze_catalog.customers'

  UNION ALL

  SELECT
    lt.source_table,
    tl.target_table,
    tl.event_time,
    lt.depth + 1
  FROM lineage_tree lt
  JOIN system.lineage.table_lineage tl
    ON lt.target_table = tl.source_table
  WHERE lt.depth < 3
)
SELECT DISTINCT
  CONCAT(REPEAT('  ', depth - 1), target_table) AS hierarchy,
  MAX(event_time) AS last_update
FROM lineage_tree
GROUP BY target_table, depth
ORDER BY depth, target_table;
```

**Output:**
```
hierarchy                                   | last_update
============================================|====================
bronze_catalog.customers                    | 2026-04-09 10:00:00
  silver_crm.customers_normalized           | 2026-04-09 10:15:00
    gold_catalog.sales.dim_cliente          | 2026-04-09 10:30:00
    gold_catalog.marketing.dim_cliente_mkt  | 2026-04-09 10:35:00
      gold_catalog.dashboards.customers_360 | 2026-04-09 11:00:00
```

---

## Gotchas

| Gotcha                              | Solução                                          |
|-------------------------------------|------------------------------------------------|
| Linhagem gaps em pipelines legados  | Migrara para SDP (Spark Declarative Pipelines) |
| Shortcut não rastreia em system.lineage | Documentar manualmente em LINEAGE.md          |
| Mirroring com latência > 5 min      | Verificar conectividade entre Workspaces       |
| Deletar tabela = linhagem perdida   | Backup em Delta Time Travel antes de DROP      |
