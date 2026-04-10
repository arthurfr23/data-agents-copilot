# Unity Catalog — Regras e Padrões

**Propósito:** Referência rápida para hierarquia, grants, volumes e tables de sistema no Unity Catalog.

---

## Hierarquia Obrigatória: Catalog.Schema.Table

A três níveis é **mandatória**. Nunca use `hive_metastore` (legado).

```sql
-- ✅ CORRETO
CREATE TABLE main.analytics.users (id INT, name STRING);

-- ❌ ERRADO
CREATE TABLE users (id INT, name STRING);  -- Usa hive_metastore
```

**Gotcha:** Tabelas sem catalog explícito caem no metastore legado. Verifique com:
```sql
SELECT catalog_name FROM system.information_schema.tables
WHERE table_name = 'users';
```

---

## Grants e Revoke — Padrão de Controle

Use sempre `GRANT` / `REVOKE` para segurança granular por grupo.

| Nível | Escopo | Sintaxe |
|-------|--------|---------|
| **Catalog** | Acesso ao catálogo inteiro | `GRANT USE CATALOG ON CATALOG main TO \`group\`` |
| **Schema** | Acesso a esquema | `GRANT USE SCHEMA ON SCHEMA main.analytics TO \`group\`` |
| **Table** | Leitura/escrita de tabela | `GRANT SELECT ON TABLE main.analytics.users TO \`group\`` |
| **Volume** | Arquivos em volume | `GRANT READ VOLUME ON VOLUME main.raw.data TO \`group\`` |

**Ordem correta de grants:**
1. USE CATALOG (pré-requisito)
2. USE SCHEMA (pré-requisito)
3. SELECT/MODIFY (operação específica)

```sql
-- Sequência correta para dar acesso a data_engineers
GRANT USE CATALOG ON CATALOG main TO `data_engineers`;
GRANT USE SCHEMA ON SCHEMA main.analytics TO `data_engineers`;
GRANT SELECT, MODIFY ON TABLE main.analytics.users TO `data_engineers`;
```

**Gotcha:** Se faltar `USE CATALOG` ou `USE SCHEMA`, a tabela não aparece mesmo com SELECT.

---

## Volumes — Padrão para Arquivos Não-Tabulares

Sempre use volumes para arquivos (CSV, JSON, Parquet, imagens, etc.).

**Formato de caminho (mandatório):**
```
/Volumes/catalog/schema/volume_name/path/to/file
```

**Criar volume:**
```sql
CREATE VOLUME main.raw.landing COMMENT "Arquivos entrada não processados";
```

**Operar em volume:**
```python
# Upload de arquivo
upload_to_volume(
    local_path="/tmp/data.csv",
    volume_path="/Volumes/main/raw/landing/data.csv"
)

# Listar conteúdo
list_volume_files(volume_path="/Volumes/main/raw/landing/")
```

**Gotcha:** Path é CASE-SENSITIVE no objeto Storage. `/Volumes/Main/Raw/...` falha se criado em minúsculas.

---

## System Tables — Fonte de Verdade para Auditoria

### Ativar Acesso a System Tables

```sql
-- Conceder acesso ao catálogo system
GRANT USE CATALOG ON CATALOG system TO `data_engineers`;
GRANT USE SCHEMA ON SCHEMA system.access TO `data_engineers`;
GRANT SELECT ON SCHEMA system.access TO `data_engineers`;
```

### Tabelas Disponíveis

| Tabela | Descrição | Filtro Crítico |
|--------|-----------|-----------------|
| `system.access.audit` | Todas ações (GRANT, DELETE, etc.) | `event_date >= current_date() - 7` |
| `system.access.table_lineage` | Dependências entre tabelas | `event_date >= current_date() - 7` |
| `system.billing.usage` | Consumo de DBU por workspace | `usage_date >= current_date() - 30` |
| `system.access.applied_permissions` | Permissões ativas em recursos | Nenhum (pequena) |

### Consultas Padrão

**Lineage — Tabelas que alimentam uma tabela:**
```sql
SELECT DISTINCT source_table_full_name, source_column_name
FROM system.access.table_lineage
WHERE target_table_full_name = 'main.analytics.users'
  AND event_date >= current_date() - 7;
```

**Auditoria — Mudanças recentes de permissão:**
```sql
SELECT event_time, user_identity.email, action_name, request_params
FROM system.access.audit
WHERE (action_name LIKE '%GRANT%' OR action_name LIKE '%REVOKE%')
  AND event_date >= current_date() - 30
ORDER BY event_time DESC
LIMIT 100;
```

**Billing — DBU por semana:**
```sql
SELECT workspace_id, sku_name, usage_date, SUM(usage_quantity) AS dbus
FROM system.billing.usage
WHERE usage_date >= current_date() - 30
GROUP BY workspace_id, sku_name, usage_date;
```

**Gotcha:** System tables precisam de `event_date` ou `usage_date` filtrado. Sem filtro, query timeout. Retenção padrão é 30 dias; verifique com seu workspace.

---

## Boas Práticas Críticas

### 1. Sempre Filtrar System Tables por Data
```sql
-- ✅ RÁPIDO (< 1s)
SELECT * FROM system.access.audit
WHERE event_date >= current_date() - 7;

-- ❌ LENTO/TIMEOUT
SELECT * FROM system.access.audit;  -- Varredura de 30 dias
```

### 2. Nunca Use hive_metastore Explicitamente
```sql
-- ✅ Novo padrão
CREATE TABLE main.analytics.users AS SELECT * FROM external_system;

-- ❌ Legado — evitar
CREATE TABLE hive_metastore.default.users AS SELECT ...;
```

### 3. Volumes — Sempre Path Completo
```python
# ✅ Correto
volume_path="/Volumes/main/raw/landing/file.csv"

# ❌ Incompleto
volume_path="landing/file.csv"  # Será interpretado como local
```

### 4. Grants — Validar com Information Schema
```sql
-- Validar permissões atribuídas
SELECT principal, action_type
FROM system.information_schema.applicable_privileges
WHERE table_name = 'users';
```

### 5. Lineage — Múltiplos Níveis
```sql
-- Mostrar cadeia completa: A -> B -> C
WITH RECURSIVE lineage AS (
  SELECT source_table_full_name, target_table_full_name, 1 AS level
  FROM system.access.table_lineage
  WHERE target_table_full_name = 'main.analytics.dashboard_source'
    AND event_date >= current_date() - 7

  UNION ALL

  SELECT tl.source_table_full_name, tl.target_table_full_name, l.level + 1
  FROM system.access.table_lineage tl
  JOIN lineage l ON tl.target_table_full_name = l.source_table_full_name
  WHERE tl.event_date >= current_date() - 7 AND l.level < 5
)
SELECT * FROM lineage ORDER BY level;
```

---

## Matriz de Decisão: Onde Armazenar Dados?

| Tipo de Dado | Armazenamento | Exemplo |
|--------------|---------------|---------|
| **Tabular estruturado** | Tabela UC (Parquet Delta) | Clientes, pedidos, logs |
| **Arquivo não-tabular** | Volume UC | CSV bruto, JSON, imagens, PDFs |
| **Dados temporários** | Tabela TEMP (sessão) | Cálculos intermediários |
| **Cache para BI** | Tabela external (Hive) | Deprecated — migrar para UC |

---

## Checklist Implementação

- [ ] Todos os catalogs têm 3 níveis (catalog.schema.table)
- [ ] System tables habilitadas para data_engineers
- [ ] Lineage queries testadas e agendadas
- [ ] Volumes criados para arquivos não-tabulares
- [ ] Grants validados com `information_schema.applicable_privileges`
- [ ] Alertas configurados para mudanças em `system.access.audit`
