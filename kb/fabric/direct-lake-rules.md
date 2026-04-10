# KB: Regras Direct Lake (Power BI Integration)

**Domínio:** Otimização de tabelas para Direct Lake, regras de cardinalidade, e integração Power BI.
**Palavras-chave:** Direct Lake, V-Order, CLUSTER BY, TMDL, DAX Query, Semantic Model.

---

## O que é Direct Lake?

Direct Lake permite Power BI consultar tabelas Gold diretamente no Lakehouse (sem import/cache):

| Propriedade | Vantagem | Limitação |
|-------------|----------|-----------|
| **Latência** | Real-time (< 1s) | Sem cache local |
| **Armazenamento** | Zero (no Power BI) | Depende OneLake availability |
| **Transformação** | Spark SQL transparente | Regras estritas de schema |
| **Custo** | Pay-as-you-go (queries) | Sem compactação BI |

**Fallback:** Direct Lake → Import Mode automaticamente se falhar validação.

---

## Regra 1: V-Order Obrigatório em Gold

Todas as tabelas Gold **DEVEM** ser escritas com V-Order:

```python
# CORRETO
df.write.format("delta") \
  .option("delta.enableVOrderedWrite", "true") \
  .mode("overwrite") \
  .option("path", "abfss://.../Gold/Sales/fact_orders/") \
  .saveAsTable("fact_orders")

# ERRADO - falhará Direct Lake
df.write.format("delta") \
  .mode("overwrite") \
  .option("path", "abfss://.../Gold/Sales/fact_orders/") \
  .saveAsTable("fact_orders")
```

**Validação:** Inspecione `_delta_log` para `vorderingJson`:
```bash
spark.sql("SELECT * FROM delta.`path`").explain()  # Procure "vorder=true"
```

---

## Regra 2: CLUSTER BY, Nunca PARTITION BY

**PARTITION BY causa fallback automático para Import Mode.**

```sql
-- CORRETO (clustering para cardinality alta)
CREATE TABLE gold.fact_sales AS
SELECT *
FROM silver.stg_sales
CLUSTER BY (date, store_id, customer_id);

-- ERRADO (causa fallback)
CREATE TABLE gold.fact_sales AS
SELECT *
FROM silver.stg_sales
PARTITION BY YEAR(order_date);
```

| Operação | Resultado | Razão |
|----------|-----------|-------|
| `PARTITION BY` | Fallback → Import | Incompatível com Direct Lake |
| `CLUSTER BY` | ✓ Direct Lake OK | Otimiza I/O sem transações |
| Sem clustering | ✓ Direct Lake OK | Menos performance, mas funciona |

**Gotcha:** `CLUSTER BY` não é transacional (diferente de `PARTITION BY`). Reaplique a cada escrita.

---

## Regra 3: Tipos de Coluna (Schema Rules)

### Datas: DATE, Não TIMESTAMP

```sql
-- CORRETO
CREATE TABLE gold.dim_date (
  date_id DATE PRIMARY KEY,
  year_num INT,
  month_num INT
);

-- ERRADO - Direct Lake rejeita
CREATE TABLE gold.dim_date (
  date_ts TIMESTAMP PRIMARY KEY,
  year_num INT
);
```

**Razão:** Power BI calendários esperam DATE; TIMESTAMP causa problemas de granularidade.

### Surrogate Keys: BIGINT

```sql
-- CORRETO
CREATE TABLE gold.dim_customer (
  customer_key BIGINT PRIMARY KEY,
  customer_id VARCHAR(50),
  name VARCHAR(200)
);

-- Usar BIGINT, não INT (evita overflow)
```

### Evite Tipos Complexos

| Tipo | Direct Lake | Nota |
|------|------------|------|
| DECIMAL(18,2) | ✓ | OK para moeda |
| BINARY | ✗ | Rejeita |
| MAP<K,V> | ✗ | Structs aninhados |
| ARRAY<T> | ✓ Limitado | Use com cuidado |
| TIMESTAMP_NTZ | ✗ | Use DATE + TIME |

---

## Regra 4: Limites de Cardinalidade

Direct Lake impõe limites para performance:

| Métrica | Limite | Ação se Excedido |
|---------|--------|-----------------|
| Colunas por tabela | 500 | Erro na conexão |
| Linhas (fact table) | 2B+ | Fallback → Import (>2B lento) |
| Dimensões únicas | 100M | Fallback se cardinality alta |
| Valores distintos/coluna | 1M+ | OK, mas filtro BI pode ser lento |

**Dica:** Teste `SELECT DISTINCT COUNT(*)` antes de conectar ao Power BI.

---

## Regra 5: Framing (Relacionamentos Fact-Dimension)

Direct Lake exige schema **star schema** bem definido:

```sql
-- CORRETO (star schema)
CREATE TABLE gold.fact_sales (
  fact_key BIGINT,
  date_key BIGINT,        -- FK para dim_date
  customer_key BIGINT,    -- FK para dim_customer
  product_key BIGINT,     -- FK para dim_product
  amount DECIMAL(18,2),
  quantity INT
) CLUSTER BY (date_key, customer_key);

CREATE TABLE gold.dim_date (
  date_key BIGINT PRIMARY KEY,
  date_id DATE,
  year INT,
  month INT
) CLUSTER BY (date_key);

-- ERRADO (denormalized, causa problemas Direct Lake)
CREATE TABLE gold.denormalized_sales (
  order_id BIGINT,
  customer_name VARCHAR(200),
  product_name VARCHAR(200),
  date TIMESTAMP,
  category VARCHAR(100),
  amount DECIMAL(18,2)
);
```

**Regra:** Many-to-One relationships only (Fact → Dimensions).

---

## Criação de Semantic Model via TMDL

Direct Lake requer definição TMDL (Tabular Model Definition Language):

### Obter Definição Atual
```http
GET /workspaces/{workspace-id}/items/{model-id}/getDefinition
Response: { "definition": "base64-encoded-tmdl" }
```

### Atualizar Modelo (LRO Pattern)
```http
PATCH /workspaces/{workspace-id}/items/{model-id}/updateDefinition
Content-Type: application/json

{
  "definition": "base64-encoded-model-definition"
}

Response:
{
  "operationId": "123e4567-e89b-12d3-a456-426614174000"
}
```

### Polling para LRO (Long-Running Operation)
```http
GET /workspaces/{workspace-id}/operations/{operationId}

{
  "status": "InProgress",
  "resultUri": "/items/{model-id}/getDefinition"
}
```

**Padrão TMDL Mínimo:**
```json
{
  "compatibility": {
    "compatibilityLevel": 1604
  },
  "model": {
    "tables": [
      {
        "name": "fact_sales",
        "columns": [
          {
            "name": "amount",
            "dataType": "decimal",
            "dataCategory": "Measure"
          }
        ]
      }
    ],
    "relationships": [
      {
        "name": "fk_date",
        "fromColumn": "fact_sales[date_key]",
        "toColumn": "dim_date[date_key]"
      }
    ]
  }
}
```

---

## Fallback Triggers (Direct Lake → Import)

Estes cenários causam fallback automático:

| Trigger | Sintoma | Fix |
|---------|---------|-----|
| V-Order ausente | "Direct Lake not available" | Reescrever com V-Order |
| PARTITION BY | Fallback silencioso | Remover partições, usar CLUSTER BY |
| Cardinalidade > 2B | Timeout em Direct Lake | Arquivar dados antigos |
| TIMESTAMP (date col) | Schema validation fail | Converter para DATE |
| Coluna BINARY | Type mismatch | Remover coluna ou converter |

**Debug:** Verifique `DAX Studio` → "Direct Lake" checkbox para confirmar status.

---

## Power BI DAX Query Execution

Executar queries DAX via REST API (Direct Lake):

```http
POST /groups/{workspace-id}/datasets/{model-id}/executeQueries
Content-Type: application/json

{
  "queries": [
    {
      "query": "EVALUATE SUMMARIZECOLUMNS(...)"
    }
  ]
}
```

**Resposta:**
```json
{
  "results": [
    {
      "tables": [
        {
          "rows": [
            { "column1": "value1" }
          ]
        }
      ]
    }
  ]
}
```

---

## Decision Tree: Direct Lake vs Import

```
Devo usar Direct Lake?
├─ Dados > 2GB? → Sim
│  └─ Schema é star schema? → Sim
│     └─ V-Order aplicado? → Sim
│        └─ CLUSTER BY (no PARTITION BY)? → Sim
│           └─ Direct Lake OK ✓
│           └─ Não → Falha, use Import
│        └─ Não → Reescrever com V-Order
│     └─ Não → Redesenhar schema
│  └─ Não → Considere Import (mais rápido)
└─ Real-time é crítico? → Não
   └─ Use Import Mode (cache, menos query cost)
```

---

## Checklist Pre-Deployment

- [ ] Tabelas Gold com V-Order habilitado
- [ ] Sem `PARTITION BY` (use `CLUSTER BY`)
- [ ] Colunas de data como `DATE` (não `TIMESTAMP`)
- [ ] Schema validado: star schema com FK explícitas
- [ ] Cardinalidade testada: `SELECT DISTINCT COUNT(*)`
- [ ] TMDL gerada e atualizada via updateDefinition
- [ ] Fallback behavior documentado
- [ ] DAX queries testadas via REST API
- [ ] Sensitivity labels aplicadas (PII)
