# Cross-Platform: Fabric ↔ Databricks

Estratégias para movimentação de dados entre Microsoft Fabric e Databricks mantendo eficiência e evitar duplicações.

---

## Matriz de Decisão: 3 Estratégias Prioritárias

| Estratégia | Custo | Latência | Complexidade | Quando usar |
|-----------|-------|----------|--------------|------------|
| **1. ABFSS Compartilhado** | Mínimo | Baixa | Baixa | Mesma conta storage (recomendado) |
| **2. OneLake Shortcuts** | Mínimo | Muito baixa | Média | Leitura zero-copy Fabric → Databricks |
| **3. Export/Upload API** | Médio | Alta | Alta | Storage accounts separados |

---

## 1. ABFSS Compartilhado (Recomendado)

### Pré-requisitos
- **Fabric e Databricks na mesma conta Azure Storage**
- Unity Catalog no Databricks
- Permissões RBAC configuradas (Storage Blob Data Contributor)

### Formato do Caminho ABFSS

```
# Fabric (OneLake via ADLS Gen2)
abfss://container@storageaccount.dfs.core.windows.net/path/to/data

# Databricks (External Location pointing to ABFSS)
abfss://workspace-root@storageaccount.dfs.core.windows.net/path/to/data
```

### Setup no Databricks

```sql
-- 1. Criar External Location
CREATE EXTERNAL LOCATION fabric_shared
  URL = 'abfss://container@storageaccount.dfs.core.windows.net/'
  WITH (CREDENTIAL = 'your-credential-name');

-- 2. Criar Schema no Catalog
CREATE SCHEMA IF NOT EXISTS main.fabric_imported USING EXTERNAL LOCATION fabric_shared;

-- 3. Registrar tabelas já existentes no ABFSS (Unity Catalog)
CREATE EXTERNAL TABLE IF NOT EXISTS main.fabric_imported.vendas_fabric
  USING PARQUET
  LOCATION 'abfss://container@storageaccount.dfs.core.windows.net/fabric/vendas/';

-- 4. Consultar como tabela normal
SELECT COUNT(*) FROM main.fabric_imported.vendas_fabric;
```

### Pipeline Databricks lendo ABFSS

```sql
CREATE OR REFRESH STREAMING TABLE bronze_fabric_vendas
CLUSTER BY (data_evento)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  'abfss://container@storageaccount.dfs.core.windows.net/fabric/vendas/',
  format => 'parquet'
);
```

### Vantagens
- Zero overhead de movimentação
- Transações ACID compartilhadas via Delta
- Permissões gerenciadas no Azure RBAC
- Ideal para arquivos Parquet/Delta

---

## 2. OneLake Shortcuts (Zero-Copy)

### Conceito
Atalhos (shortcuts) são links diretos entre OneLake (Fabric) e Lakehouse (Databricks) **sem copiar dados**.

### Criar Shortcut via API REST

```bash
# 1. Authenticate to Fabric
TOKEN=$(az account get-access-token --query accessToken -o tsv)

# 2. Create Shortcut in Fabric Lakehouse
curl -X POST \
  "https://api.fabric.microsoft.com/v1/workspaces/{workspace-id}/lakehouses/{lakehouse-id}/shortcuts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "vendas_databricks",
    "target": {
      "onelakeLocationObjectReference": {
        "itemId": "databricks-lakehouse-id",
        "workspaceId": "databricks-workspace-id",
        "path": "/Tables/vendas"
      }
    }
  }'
```

### Consumir no Databricks

```sql
-- Databricks vê o shortcut como tabela virtual
SELECT COUNT(*) FROM main.silver.vendas_fabric_shortcut;

-- Pode transformar sem copiar
CREATE OR REFRESH MATERIALIZED VIEW gold_summary AS
SELECT
  DATE_TRUNC('month', data_evento) AS mes,
  COUNT(*) AS total_vendas,
  SUM(valor) AS receita
FROM main.silver.vendas_fabric_shortcut
GROUP BY DATE_TRUNC('month', data_evento);
```

### Limitações
- Leitura apenas (não escrita)
- Suporta tabelas Parquet e Delta
- Sincronização eventual (não transacional)

---

## 3. Export/Upload via OneLake API

### Cenário
Storage accounts separados, movimentação controlada de dados.

### Padrão 1: Fabric → Databricks (Export)

```python
# Python no Fabric Notebook
import requests
from pyspark.sql import SparkSession

# 1. Ler dados no Fabric
df = spark.read.parquet("/Volumes/my_lakehouse/Tables/vendas")

# 2. Exportar para blob temporário
df.write.mode("overwrite").parquet("abfss://export@container.dfs.core.windows.net/vendas_export/")

# 3. Notificar Databricks via webhook/API
requests.post("https://databricks-workspace/api/2.1/jobs/run-now",
  json={"job_id": 123, "job_parameters": {"source_path": "abfss://export@..."}})
```

### Padrão 2: Databricks → Fabric (Upload)

```python
# Python no Databricks
from databricks.sdk import WorkspaceClient
import requests

w = WorkspaceClient()

# 1. Ler dados no Databricks
df = spark.read.table("main.gold.vendas_summary")

# 2. Gravar em ADLS Gen2 temporário (Databricks side)
df.write.mode("overwrite").parquet("abfss://staging@source.dfs.core.windows.net/")

# 3. Fabric lê via shortcut ou ABFSS (se mesma storage account)
# ou inicia cópia assíncrona via Copy Activity no Data Factory
```

### Data Factory Copy Activity (Hybrid Orchestration)

```yaml
# Azure Data Factory pipeline
activities:
  - name: CopyDatabricksToFabric
    type: Copy
    inputs:
      - referenceName: DatabricksDataset
        type: DatasetReference
    outputs:
      - referenceName: FabricDataset
        type: DatasetReference
    typeProperties:
      source:
        type: AzureDataLakeStoreSource
        recursive: true
      sink:
        type: AzureDataLakeStoreSink
```

---

## Mapeamento de Tipos Entre Plataformas

| Databricks (Delta Lake) | Fabric (OneLake) | Comportamento |
|-------------------------|-----------------|---------------|
| INT / BIGINT | int32 / int64 | 1:1 |
| DECIMAL(p,s) | decimal(p,s) | 1:1 com precisão |
| STRING | string | UTF-8 válido |
| DATE | date | 1:1 |
| TIMESTAMP | timestamp | Timezone: UTC recommended |
| ARRAY<T> | array<T> | Suportado em Parquet |
| STRUCT<...> | object | Flattening necessário |
| MAP | ❌ | Converter ARRAY de KV pairs |

---

## Exemplo Completo: Bronze Fabric → Silver Databricks

### Fabric (exporta dados diariamente)

```python
# Fabric Notebook
from datetime import datetime

# 1. Ler tabela Fabric
df_vendas = spark.read.table("fabric_db.vendas")

# 2. Filtrar últimos dias
from pyspark.sql.functions import col, current_date, datediff
df_recent = df_vendas.filter(datediff(current_date(), col("data_evento")) <= 7)

# 3. Salvar em ABFSS compartilhado
df_recent.write \
  .mode("overwrite") \
  .parquet(f"abfss://shared@storage.dfs.core.windows.net/fabric_export/{datetime.now().strftime('%Y%m%d')}/")
```

### Databricks (consome via Auto Loader)

```sql
-- Databricks Auto Loader pipeline
CREATE OR REFRESH STREAMING TABLE bronze_fabric_vendas
CLUSTER BY (data_evento)
AS
SELECT
  *,
  _metadata.file_path AS source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  'abfss://shared@storage.dfs.core.windows.net/fabric_export/',
  format => 'parquet',
  cloudFiles.inferColumnTypes => 'true'
);

-- Silver: tipagem e validação
CREATE OR REFRESH STREAMING TABLE silver_vendas
CLUSTER BY (id_cliente, data_evento)
AS
SELECT
  CAST(id_venda AS BIGINT),
  CAST(id_cliente AS BIGINT),
  CAST(valor_total AS DECIMAL(18,2)),
  CAST(data_evento AS DATE),
  _ingested_at
FROM stream(bronze_fabric_vendas)
WHERE id_venda IS NOT NULL;
```

---

## Checklist de Configuração

- [ ] Storage account ou OneLake accessível de ambas as plataformas
- [ ] ABFSS paths testados com `dbutils.fs.ls()`
- [ ] Unity Catalog External Location criado
- [ ] Permissões RBAC (Storage Blob Data Contributor) configuradas
- [ ] Auto Loader pipeline validado com dados reais
- [ ] OneLake Shortcuts criados (se estratégia #2)
- [ ] Mapeamento de tipos conferido
- [ ] Data Factory pipeline testada (se estratégia #3)
- [ ] Monitoramento de freshness ativado (SLA na Silver)
