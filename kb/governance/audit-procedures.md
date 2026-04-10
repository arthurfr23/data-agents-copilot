# Audit Procedures — Procedimentos de Auditoria

**Último update:** 2026-04-09
**Domínio:** Auditoria de acesso, modificações de dados, conformidade
**Plataformas:** Databricks (system.access.audit), Azure Fabric (OneLake Catalog)

---

## Databricks — system.access.audit

### Estrutura da Tabela

```sql
-- Tabela de auditoria sistema (read-only)
SELECT
  event_id,
  actor_email,
  action_type,
  object_type,
  object_id,
  new_value,
  request_params,
  event_time,
  event_date
FROM system.access.audit
LIMIT 5;
```

| Campo          | Tipo        | Descrição                                     |
|----------------|-------------|-----------------------------------------------|
| **event_id**   | STRING      | ID único do evento de auditoria               |
| **actor_email**| STRING      | Email do usuário que executou a ação          |
| **action_type**| STRING      | CREATE, READ, MODIFY, DELETE, GRANT, REVOKE  |
| **object_type**| STRING      | TABLE, SCHEMA, CATALOG, VOLUME, CLUSTER       |
| **object_id**  | STRING      | ID qualificado (ex: catalog.schema.table)     |
| **new_value**  | VARIANT     | Valor anterior/novo para mudanças             |
| **event_time** | TIMESTAMP   | Timestamp exato do evento                      |
| **event_date** | DATE        | Data do evento (coluna particionada)          |

### Regra Crítica: Sempre Filtrar por event_date

```sql
-- ✅ EFICIENTE (filtra partição)
SELECT *
FROM system.access.audit
WHERE event_date >= CURRENT_DATE() - 30;

-- ❌ INEFICIENTE (full scan)
SELECT *
FROM system.access.audit
WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAY;
```

---

## Consultas de Auditoria Comuns

### 1. Quem Acessou Qual Tabela?

```sql
-- Últimos 7 dias: acessos a tabelas sensíveis
SELECT
  actor_email,
  action_type,
  object_type,
  object_id,
  event_time,
  COUNT(*) AS num_acessos
FROM system.access.audit
WHERE event_date >= CURRENT_DATE() - 7
  AND (object_id LIKE '%dim_cliente%'
       OR object_id LIKE '%fact_vendas%'
       OR object_id LIKE '%PII%')
GROUP BY actor_email, action_type, object_type, object_id, event_time
ORDER BY event_time DESC;
```

### 2. Tentativas de Acesso Negado

```sql
-- Falhas de autenticação e permissão
SELECT
  actor_email,
  object_id,
  action_type,
  request_params,
  event_time
FROM system.access.audit
WHERE event_date >= CURRENT_DATE() - 7
  AND (action_type = 'DENIED_PERMISSION'
       OR action_type = 'FAILED_AUTHENTICATION');
```

### 3. Modificações de Dados (DML)

```sql
-- Últimos 30 dias: INSERT/UPDATE/DELETE
SELECT
  actor_email,
  object_id,
  action_type,
  new_value,
  event_time
FROM system.access.audit
WHERE event_date >= CURRENT_DATE() - 30
  AND action_type IN ('MODIFY', 'INSERT', 'DELETE')
  AND object_type = 'TABLE'
ORDER BY event_time DESC;
```

### 4. Mudanças de Permissões (GRANT/REVOKE)

```sql
-- Últimos 90 dias: alterações de acesso
SELECT
  actor_email,
  action_type,
  object_id,
  request_params,  -- Contém detalhes do GRANT/REVOKE
  event_time
FROM system.access.audit
WHERE event_date >= CURRENT_DATE() - 90
  AND action_type IN ('GRANT', 'REVOKE')
ORDER BY event_time DESC;
```

### 5. Atividade por Usuário (Behavior Analytics)

```sql
-- Usuários com atividade fora do padrão
SELECT
  actor_email,
  COUNT(*) AS num_acessos,
  COUNT(DISTINCT object_id) AS tabelas_acessadas,
  COUNT(DISTINCT action_type) AS tipos_acao,
  MIN(event_time) AS primeiro_acesso,
  MAX(event_time) AS ultimo_acesso
FROM system.access.audit
WHERE event_date >= CURRENT_DATE() - 7
GROUP BY actor_email
HAVING COUNT(*) > 1000  -- Threshold de atividade
ORDER BY num_acessos DESC;
```

---

## Azure Fabric — OneLake Catalog Audit

### Consultar Auditoria no Fabric

```python
# Usando mcp__fabric_community__get_lineage com auditoria
from fabric_client import audit

# Últimos 7 dias de atividade
audit_logs = audit.get_audit_logs(
    days=7,
    activity_types=['Access', 'Modify', 'Delete', 'Share']
)

for log in audit_logs:
    print(f"{log['timestamp']} | {log['user']} | {log['activity']} | {log['item_name']}")
```

### Via SQL (Fabric Warehouse)

```sql
-- OneLake Catalog (integrado com Workspace)
SELECT
  audit_timestamp,
  user_email,
  activity,
  item_id,
  item_name,
  item_type,
  details
FROM fabric_system.audit_logs
WHERE audit_timestamp >= CAST(GETDATE() - 7 AS DATE)
ORDER BY audit_timestamp DESC;
```

---

## Frequência de Auditoria Recomendada

| Tipo de Auditoria           | Frequência        | Responsável        | Retenção  |
|-----------------------------|-------------------|--------------------|-----------|
| Acessos a PII               | Diária (automático) | Data Governance    | 2 anos    |
| Mudanças de permissões      | Semanal           | Security team      | 3 anos    |
| Modificações em tabelas Gold| Semanal           | Data Engineering   | 1 ano     |
| Conformidade LGPD/GDPR      | Trimestral (manual)| Legal/Compliance   | 5 anos    |
| Right to Erasure            | Manual            | Data Governance    | 7 anos    |

---

## Template de Relatório de Auditoria Trimestral

### audit_report_Q2_2026.md

```markdown
# Relatório de Auditoria — Q2 2026 (Abr-Jun)

## 1. Resumo Executivo
- **Período:** 2026-04-01 a 2026-06-30
- **Tabelas Auditadas:** 145 (Gold layer)
- **Total de Acessos:** 2.3M
- **Falhas de Segurança:** 0
- **Status:** ✅ CONFORME

## 2. Acesso a Dados Sensíveis
### PII/Restrito (dim_cliente, etc)
- **Acessos:** 12.5K (período)
- **Usuários Únicos:** 23
- **Permissões Revogadas:** 2 (offboarding)
- **Acessos Anômalos:** 0

### Confidencial (financeiro)
- **Acessos:** 5.2K (período)
- **Usuários Únicos:** 8 (aprovados)
- **Tentativas Negadas:** 1 (usuário sem permissão)
- **Ação Tomada:** Educação do usuário

## 3. Modificações de Dados
- **INSERT:** 845.3K registros
- **UPDATE:** 234.1K registros
- **DELETE:** 0 (nenhuma deleção fora de SCD2)
- **Modificações DDL:** 12 (alterações de schema)

## 4. Conformidade LGPD
✅ Todos os dados PII mascarados em DEV
✅ Right to Erasure: 3 pedidos processados (0 dias avg)
✅ Data Retention: 0 violações
✅ Consent Management: atualizado

## 5. Recomendações
1. Implementar monitoramento automático de acessos anômalos
2. Treinamento de segurança para 5 novos colaboradores
3. Migração de pipelines legados para SDP (3 ainda em DLT)

---
**Data do Relatório:** 2026-07-01
**Preparado por:** Data Governance Team
**Revisado por:** Legal/Compliance
```

---

## Automação: Pipeline de Auditoria Diária

```sql
-- Tabela para armazenar auditorias consolidadas
CREATE TABLE gold_catalog.governance.audit_summary (
  audit_date DATE,
  event_type STRING,  -- 'access', 'modification', 'permission_change'
  object_id STRING,
  num_events INT,
  actors_involved INT,
  status STRING,  -- 'normal', 'warning', 'critical'
  notes STRING,
  created_at TIMESTAMP
);

-- Pipeline diário (executar 01:00)
INSERT INTO gold_catalog.governance.audit_summary
SELECT
  CAST(event_date AS DATE),
  CASE
    WHEN action_type IN ('READ', 'DESCRIBE') THEN 'access'
    WHEN action_type IN ('INSERT', 'UPDATE', 'DELETE', 'MODIFY') THEN 'modification'
    WHEN action_type IN ('GRANT', 'REVOKE') THEN 'permission_change'
    ELSE 'other'
  END AS event_type,
  object_id,
  COUNT(*) AS num_events,
  COUNT(DISTINCT actor_email) AS actors_involved,
  CASE
    WHEN COUNT(*) > 10000 THEN 'warning'  -- Atividade anormal
    WHEN object_id LIKE '%PII%' AND COUNT(*) > 100 THEN 'critical'
    ELSE 'normal'
  END AS status,
  CONCAT('Últimos 30 dias: ', COUNT(*), ' eventos por ', COUNT(DISTINCT actor_email), ' atores'),
  CURRENT_TIMESTAMP()
FROM system.access.audit
WHERE event_date >= CURRENT_DATE() - 1
GROUP BY event_date, event_type, object_id;
```

---

## Gotchas

| Gotcha                              | Solução                                    |
|-------------------------------------|--------------------------------------------|
| Auditoria incompleta sem filtro event_date | SEMPRE filtrar por event_date (partição) |
| Dados sensíveis logados em audit    | system.access.audit não contém valores PII|
| Retenção de audit = 90 dias padrão  | Exportar para Iceberg para retenção longa |
| Atraso entre ação e registro        | Permitir até 5 min para sincronização      |
