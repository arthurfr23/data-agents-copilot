# KB: Padrões de Lakehouse e OneLake

**Domínio:** Arquitetura de Lakehouse, armazenamento unificado com OneLake, e organização Medallion.
**Palavras-chave:** Delta Lake, V-Order, ABFSS, Medallion, Schemas, Bronze/Silver/Gold.

---

## Conceitos Fundamentais

### OneLake como Armazenamento Unificado

OneLake é o armazenamento cloud nativo do Fabric, acessível via ABFSS (Azure Blob File System Secure):

```
abfss://workspace@onelake.dfs.fabric.microsoft.com/lakehouse.Lakehouse/
```

- Um OneLake por tenant, multi-workspaces
- Suporta shortcuts para zero-copy access
- Integração nativa com Spark, SQL, Power BI
- Governança via workspace roles e sensitivity labels

**REST API (criação de Lakehouse):**
```
POST /workspaces/{id}/lakehouses
Content-Type: application/json

{
  "displayName": "SalesLakehouse",
  "description": "Lakehouse for sales analytics",
  "creationPayload": {
    "enableSchemas": true
  }
}
```

---

## Formato Delta Lake (Padrão)

Sempre use Delta Lake em Lakehouses Fabric (Parquet com ACID compliance):

| Aspecto                | Recomendação                              | Detalhes                                 |
|------------------------|-------------------------------------------|------------------------------------------|
| **Compressão**         | Snappy (padrão)                          | Balança taxa/velocidade                  |
| **Write Mode**         | `overwrite` com `mergeSchema`            | Permite evolução de schema                |
| **Modo Particionamento** | Por `year`, `month`, ou `date` (Gold)   | Evite excesso de partições (<1000)       |
| **Formato de Arquivo** | Parquet (.parquet)                       | Compressão colunar nativa                |

**Gotcha:** Não crie partições dinâmicas em Bronze — use apenas em Silver/Gold após transformação.

---

## Organização Medallion (Bronze → Silver → Gold)

### Bronze (Ingestion Layer)
- Cópia 1:1 dos dados brutos de fontes
- Sem transformações lógicas
- Retenção: 30-90 dias
- Estrutura: `Bronze/{source_system}/{entity_name}/`

```python
# Exemplo de ingestão
spark.write.format("delta").mode("overwrite") \
  .option("path", "abfss://.../Bronze/CRM/Customer/") \
  .saveAsTable("bronze_customer")
```

### Silver (Cleansing & Integration)
- Dados limpos, deduplicados, com regras PII aplicadas
- Joins e desnormalizações iniciais
- Retenção: 1-2 anos
- Estrutura: `Silver/{domain}/{entity_name}/`

**Padrão:** Use `MERGE` para SCD Type 2 em Silver.

### Gold (Analytics Layer)
- Dados otimizados para consumo (BI, ML, relatórios)
- Agregações pre-calculadas
- **Obrigatório:** V-Order para Direct Lake
- Retenção: 3+ anos (compliance)
- Estrutura: `Gold/{team}/{subject_area}/`

---

## V-Order (Leitura Otimizada)

**Obrigatório para Direct Lake no Power BI:**

```python
# Aplicar V-Order durante escrita
spark.write.format("delta") \
  .option("delta.enableVOrderedWrite", "true") \
  .mode("overwrite") \
  .option("path", "abfss://.../Gold/Sales/dim_customer/") \
  .saveAsTable("dim_customer_gold")
```

| Propriedade | Valor | Impacto |
|-------------|-------|--------|
| **Bytes** | ~5-10% compressão extra | Melhora I/O significativamente |
| **Encoding** | Ordinal (Order-preserving) | Acelera filtros em Power BI |
| **Scan Time** | -40 a -60% em queries | Performance Direct Lake |

**Verificação:** Inspecione `_delta_log/_current_version` para `vorderingJson`.

---

## enable_schemas (Multi-Schema Lakehouses)

Habilite schemas para organizar tables logicamente (v1.1+):

```python
# Criar lakehouse com schemas
create_lakehouse(
  workspace='Analytics',
  display_name='MainLakehouse',
  enable_schemas=True
)
```

**Estrutura com Schemas:**
```
MainLakehouse.default.customer_bronze       # schema=default
MainLakehouse.analytics.sales_gold          # schema=analytics
MainLakehouse.governance.audit_logs         # schema=governance
```

**Benefício:** Isolamento lógico sem criar lakehouses múltiplos.

---

## Tables vs Files (Divisão de Responsabilidades)

| Aspecto | Tables | Files |
|---------|--------|-------|
| **Formato** | Delta Lake (.parquet) | Parquet, CSV, JSON |
| **Transações** | ACID completo | Nenhum (immutable) |
| **Consultas** | SQL/Spark nativo | Requer leitura explícita |
| **Uso Ideal** | Dados estruturados, BI | Raw files, archives |
| **Caminho** | `/Tables/` | `/Files/` |

**Regra:** Transforme rapidamente Bronze Files → Silver/Gold Tables.

---

## Spark Pool Configuration

Fabric aloca Spark pools dinâmicos:

| Configuração | Padrão | Customização |
|--------------|--------|--------------|
| **Executors** | Auto (1-200) | Limitado pelo capacity |
| **Driver Memory** | 4GB | Não customizável |
| **Python/R Version** | 3.11 / 4.3 | Conforme workspace |
| **Timeout** | 20 min (inatividade) | Configurável (24h max) |

**Dica:** Lakehouses compartilham Spark pools com Notebooks/Pipelines — monitor `spark.sparkContext.defaultParallelism`.

---

## Managed vs Unmanaged Tables

| Propriedade | Managed | Unmanaged |
|-------------|---------|-----------|
| **Storage** | Dentro do Lakehouse (ABFSS) | Referência a path externo |
| **Ownership** | Fabric (delete table = delete data) | Usuário (delete table = keep data) |
| **REST API** | POST `{lakehouse_id}/tables` | Manual via shortcuts |
| **Recomendação** | Padrão em Fabric | Use shortcuts ao invés |

**Gotcha:** Unmanaged tables requerem path acessível — prefira shortcuts para integração cross-workspace.

---

## REST API Cheat Sheet

### Criar Lakehouse
```http
POST /workspaces/{workspace-id}/lakehouses
{
  "displayName": "AnalyticsLakehouse",
  "creationPayload": {
    "enableSchemas": true
  }
}
```

### Listar Lakehouses
```http
GET /workspaces/{workspace-id}/lakehouses
```

### Obter Detalhes Lakehouse
```http
GET /workspaces/{workspace-id}/lakehouses/{lakehouse-id}
```

### Atualizar Lakehouse
```http
PATCH /workspaces/{workspace-id}/lakehouses/{lakehouse-id}
{
  "displayName": "UpdatedLakehouse"
}
```

---

## Decision Matrix: Bronze vs Silver vs Gold

```
Quando usar Bronze:
  → Fonte externa (API, SFTP, Data Lake)
  → Dados com estrutura inconsistente
  → Auditoria de ingestão crítica

Quando usar Silver:
  → Após limpeza e validação
  → Dados prontos para joins inter-domínios
  → Necessário rastreamento de alterações (SCD Type 2)

Quando usar Gold:
  → Consumo direto em Power BI (Direct Lake)
  → Agregações pré-calculadas (fact tables)
  → Performance crítica (<2s latência)
```

---

## Checklist de Implementação

- [ ] Criar lakehouse com `enable_schemas=True`
- [ ] Estruturar diretórios: `Bronze/`, `Silver/`, `Gold/`
- [ ] Aplicar V-Order em todas as tabelas Gold
- [ ] Configurar retention policies (30d Bronze, 1y Silver, 3y Gold)
- [ ] Validar ABFSS paths acessíveis por Spark jobs
- [ ] Testar Direct Lake connection após v-order
- [ ] Documentar lineage no OneLake Catalog
