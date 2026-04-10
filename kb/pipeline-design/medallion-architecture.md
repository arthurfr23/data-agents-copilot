# Arquitetura Medallion: Regras Bronze → Silver → Gold

Padrão de camadas para pipelines data lakehouse modernos. Define o que é obrigatório, permitido e proibido em cada nível.

---

## Bronze: Ingestão Raw

**Objetivo:** Capturar dados exatamente como chegam da fonte.

### Regras Invioláveis

| Regra | Descrição | Exemplo |
|-------|-----------|---------|
| **NUNCA transforme** | Sem conversão de tipo, limpeza ou deduplicação | Aceite NULL, espaços, tipos mistos |
| **Auto Loader obrigatório** | Use `read_files()` com `cloud_files` / `cloudFiles` | `FROM STREAM read_files('/path', format => 'json')` |
| **Schema inference com rescue** | Use `schema_inference` com coluna `_rescued_data` | `cloudFiles.schemaInferenceMode: 'addNewColumns'` |
| **Apenas STREAMING TABLE** | Nunca use MATERIALIZED VIEW na Bronze | Permite append-only, incremental processing |
| **Minimal metadata** | Sempre adicione `_ingested_at`, `_file_path` | `current_timestamp() AS _ingested_at` |

### Padrão SQL

```sql
CREATE OR REFRESH STREAMING TABLE bronze_vendas
CLUSTER BY (data_carga)
AS
SELECT
  *,
  _metadata.file_path,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/raw/vendas/',
  format => 'json',
  cloudFiles.schemaInferenceMode => 'addNewColumns',
  cloudFiles.schemaLocation => '/Volumes/raw/vendas/.schema'
);
```

### Configuração SDP (databricks.yml)

```yaml
resources:
  pipelines:
    bronze_pipeline:
      configuration:
        cloudFiles.inferColumnTypes: "true"
        cloudFiles.schemaInferenceMode: "addNewColumns"
        cloudFiles.schemaLocation: "/Volumes/raw/vendas/.schema"
```

---

## Silver: Limpeza e Tipagem

**Objetivo:** Dados consistentes, validados e de qualidade.

### Regras Invioláveis

| Regra | Descrição | Impacto |
|-------|-----------|--------|
| **OBRIGATÓRIO STREAMING TABLE** | Nunca MATERIALIZED VIEW na Silver | Permite SCD2 via AUTO CDC |
| **Sempre use AUTO CDC** | Para histórico de mudanças, nunca LAG/LEAD/ROW_NUMBER | Rastreamento automático de versões |
| **expect_or_drop obrigatório** | Remove registros inválidos, não falha pipeline | Mantém pipeline resiliente |
| **Tipagem forte** | DECIMAL(p,s) para valores, STRING truncado, DATE validado | Evita erros downstream |
| **Deduplicação** | Via chave natural ou surrogate em AUTO CDC | Define `ON (coluna_chave)` |

### Padrão SQL com SCD2

```sql
CREATE OR REFRESH STREAMING TABLE silver_vendas
CLUSTER BY (id_venda, data_evento)
AS
SELECT
  id_venda,
  CAST(id_cliente AS BIGINT) AS id_cliente,
  CAST(valor_total AS DECIMAL(18,2)) AS valor_total,
  CAST(data_evento AS DATE) AS data_evento,
  status,
  _ingested_at
FROM stream(bronze_vendas)
WHERE
  id_venda IS NOT NULL
  AND valor_total > 0;

-- SCD2 com histório de mudanças
CREATE OR REFRESH STREAMING TABLE silver_vendas_history
CLUSTER BY (id_venda, __START_AT)
AS
APPLY CHANGES INTO silver_vendas_history
FROM stream(silver_vendas)
KEYS (id_venda)
SEQUENCE BY _ingested_at
COLUMNS * EXCEPT (_ingested_at);
```

### Expectations e Validação

```sql
-- Define expectations na Silver
@expect(condition = "id_cliente IS NOT NULL")
@expect_or_drop(condition = "valor_total > 0")
@expect_or_drop(condition = "UPPER(status) IN ('ATIVO', 'CANCELADO')")
SELECT * FROM stream(bronze_vendas);
```

---

## Gold: Agregações e Star Schema

**Objetivo:** Dados prontos para análise e BI.

### Regras Invioláveis

| Regra | Descrição | Detalhe |
|-------|-----------|--------|
| **MATERIALIZED VIEW obrigatória** | Para agregações finais, nunca STREAMING TABLE | Recomputa completo a cada refresh |
| **CLUSTER BY (nunca PARTITION BY)** | Liquid Clustering automático | Sem ZORDER manual necessário |
| **expect_or_fail crítico** | Bloqueia pipeline se dados inválidos | Última camada de proteção |
| **Star Schema rigoroso** | dim_* independentes, fact_* com INNER JOINs | Evita nulls em chaves estrangeiras |
| **Surrogate keys BIGINT** | Chaves primárias em dimensões | Sequência monotônica 1, 2, 3... |

### Padrão Gold: Materialized View com Cluster

```sql
-- Dimensão (NEVER from silver_entidade directly)
CREATE OR REFRESH MATERIALIZED VIEW gold_dim_cliente
CLUSTER BY (surrogate_key)
AS
SELECT
  ROW_NUMBER() OVER (ORDER BY id_cliente) AS surrogate_key,
  id_cliente,
  nome_cliente,
  cidade,
  pais,
  current_timestamp() AS _created_at
FROM silver_cliente
WHERE id_cliente IS NOT NULL
GROUP BY id_cliente, nome_cliente, cidade, pais;

-- Tabela de datas (sintética, NUNCA SELECT DISTINCT)
CREATE OR REFRESH MATERIALIZED VIEW gold_dim_data
CLUSTER BY (data)
AS
SELECT DISTINCT
  CAST(data_seq AS DATE) AS data,
  YEAR(data_seq) AS ano,
  QUARTER(data_seq) AS trimestre,
  MONTH(data_seq) AS mes,
  DAYOFWEEK(data_seq) AS dia_semana,
  WEEKOFYEAR(data_seq) AS semana
FROM (
  SELECT EXPLODE(SEQUENCE(DATE '2020-01-01', DATE '2030-12-31', INTERVAL 1 DAY)) AS data_seq
);

-- Fato com INNER JOINs
CREATE OR REFRESH MATERIALIZED VIEW gold_fact_vendas
CLUSTER BY (id_cliente, data_venda)
AS
SELECT
  dd.surrogate_key AS dim_data_key,
  dc.surrogate_key AS dim_cliente_key,
  v.id_venda,
  v.valor_total,
  v.qtd_itens,
  COUNT(*) AS qtd_transacoes
FROM silver_vendas v
INNER JOIN gold_dim_cliente dc ON v.id_cliente = dc.id_cliente
INNER JOIN gold_dim_data dd ON CAST(v.data_evento AS DATE) = dd.data
GROUP BY dd.surrogate_key, dc.surrogate_key, v.id_venda, v.valor_total, v.qtd_itens;
```

---

## Tabela Comparativa: O que é permitido por camada

| Operação | Bronze | Silver | Gold |
|----------|--------|--------|------|
| **Ingestão raw** | ✓ OBRIGATÓRIO | ✗ | ✗ |
| **Auto Loader** | ✓ OBRIGATÓRIO | ✗ | ✗ |
| **STREAMING TABLE** | ✓ OBRIGATÓRIO | ✓ OBRIGATÓRIO | ✗ |
| **MATERIALIZED VIEW** | ✗ | ✗ | ✓ OBRIGATÓRIO |
| **AUTO CDC** | ✗ | ✓ RECOMENDADO | ✗ |
| **expect (apenas alerta)** | ✗ | ✓ SIM | ✓ SIM |
| **expect_or_drop** | ✗ | ✓ OBRIGATÓRIO | ✓ SIM |
| **expect_or_fail** | ✗ | ✗ | ✓ OBRIGATÓRIO |
| **Tipagem forte** | ✗ (aceita strings) | ✓ OBRIGATÓRIO | ✓ OBRIGATÓRIO |
| **Transformações** | ✗ | ✓ SIM | ✓ SIM |
| **Agregações** | ✗ | ✗ | ✓ OBRIGATÓRIO |
| **CLUSTER BY** | ✓ SIM | ✓ SIM | ✓ OBRIGATÓRIO |
| **PARTITION BY** | ✗ | ✗ | ✗ (use CLUSTER BY) |
| **Deduplicação** | ✗ | ✓ (via CDC) | ✗ (já deduplic.) |

---

## Fluxo de Dados Recomendado

```
Cloud Storage (JSON, CSV, Parquet)
         ↓
   Auto Loader
         ↓
  bronze_*  ← Raw, com _ingested_at
         ↓
    STREAM transformação
         ↓
  silver_*  ← Tipado, validado, com expect_or_drop
         ↓
   Agregação Gold
         ↓
  gold_dim_* / gold_fact_*  ← Star Schema, CLUSTER BY
```

---

## Checklist de Implementação

- [ ] Bronze usa `read_files()` com `cloudFiles` options
- [ ] Bronze schema inference com `_rescued_data` ativado
- [ ] Bronze nunca transforma dados
- [ ] Silver usa STREAMING TABLE (não MATERIALIZED VIEW)
- [ ] Silver implementa AUTO CDC para histórico
- [ ] Silver usa `@expect_or_drop` para validação
- [ ] Gold usa MATERIALIZED VIEW (não STREAMING TABLE)
- [ ] Gold tem `dim_data` gerada via SEQUENCE + EXPLODE
- [ ] Gold fact_* faz INNER JOIN com todas as dimensões
- [ ] Gold usa CLUSTER BY em todas as tabelas
- [ ] Surrogate keys em dim_* são BIGINT com ROW_NUMBER()
