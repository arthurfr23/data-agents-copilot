# Access Control Patterns — RBAC em Databricks e Fabric

**Último update:** 2026-04-09
**Domínio:** Controle de acesso, permissões e segurança
**Plataformas:** Databricks (Unity Catalog), Azure Fabric (Workspace Roles)

---

## Databricks — Unity Catalog (RBAC)

### Estrutura de Permissões

| Objeto             | Comando GRANT/REVOKE                    | Padrão                                   |
|--------------------|------------------------------------------|------------------------------------------|
| **Catalog**        | `GRANT USAGE ON CATALOG x TO role_name` | Todos devem ter USAGE no catálogo        |
| **Schema**         | `GRANT USAGE ON SCHEMA x.y TO role_name`| USAGE padrão, CREATE para data engineers |
| **Table**          | `GRANT SELECT/MODIFY ON TABLE x.y.z`    | SELECT para analistas, MODIFY para devs  |
| **Volume**         | `GRANT READ/WRITE ON VOLUME x.y.z`      | WRITE apenas para pipelines              |
| **Function**       | `GRANT EXECUTE ON FUNCTION x.y.z`       | EXECUTE para funções customizadas        |

### Padrão de Grants Obrigatório

```sql
-- 1. Criar role para equipe
CREATE ROLE analyst_br;

-- 2. Conceder USAGE na hierarquia
GRANT USAGE ON CATALOG gold_catalog TO analyst_br;
GRANT USAGE ON SCHEMA gold_catalog.sales TO analyst_br;

-- 3. Conceder SELECT apenas nas tabelas necessárias
GRANT SELECT ON TABLE gold_catalog.sales.fact_vendas TO analyst_br;
GRANT SELECT ON TABLE gold_catalog.sales.dim_cliente TO analyst_br;

-- 4. Atribuir role ao grupo do AAD/Okta
GRANT ROLE analyst_br TO GROUP 'analysts@empresa.com.br';
```

### Row-Level Security (RLS) via Dynamic Views

```sql
-- Mascarar dados por região do usuário
CREATE VIEW gold_catalog.sales.fact_vendas_rls AS
SELECT
  *
EXCEPT (valor_unitario)  -- Ocultar coluna sensível
FROM gold_catalog.sales.fact_vendas
WHERE regiao = CURRENT_USER_GROUP('regiao_acesso');

GRANT SELECT ON VIEW gold_catalog.sales.fact_vendas_rls TO analyst_br;
```

### Column Masking

```sql
-- Mascarar CPF em visão pública
CREATE VIEW gold_catalog.customers.dim_cliente_public AS
SELECT
  id_cliente,
  CONCAT(SUBSTRING(cpf, 1, 3), '***-**') AS cpf_masked,
  email
FROM gold_catalog.customers.dim_cliente;
```

---

## Azure Fabric — Workspace Roles

### Hierarquia de Permissões

| Papel          | Criar Itens | Modificar | Executar | Publicar | Admin |
|----------------|-------------|----------|----------|----------|-------|
| **Admin**      | ✅          | ✅       | ✅       | ✅       | ✅    |
| **Contributor** | ✅          | ✅       | ✅       | ✅       | ❌    |
| **Member**     | ❌          | Próprio  | ✅       | ❌       | ❌    |
| **Viewer**     | ❌          | ❌       | ✅       | ❌       | ❌    |

### Atribuição de Papéis (Fabric)

```
Workspace → Manage Access → Add People

1. Data Engineer:      Contributor (pode publicar)
2. BI Analyst:         Contributor + OneLake acesso READ
3. Business User:      Viewer (relatórios apenas)
4. Data Governance:    Admin (auditoria e segurança)
```

### OneLake Security

```sql
-- Fabric Lakehouse: segurança via papéis + sensitivity labels
-- 1. Criar sensitivity label: "Confidencial - Financeiro"
-- 2. Aplicar a colunas no Semantic Model
-- 3. Fabric bloqueia acesso automático para usuários sem permissão
```

---

## Princípios Críticos

### 1. Nunca Conceda Acesso Direto a Usuários

❌ **ERRADO:**
```sql
GRANT SELECT ON TABLE gold_catalog.sales.fact_vendas TO user@empresa.com.br;
```

✅ **CERTO:**
```sql
-- Criar grupo no AAD/Okta primeiro
-- GRANT a grupo, nunca a usuário individual
GRANT SELECT ON TABLE gold_catalog.sales.fact_vendas TO GROUP 'analysts@empresa.com.br';
```

**Razão:** Facilita offboarding (remover do grupo revoga acesso) e auditoria centralizada.

### 2. Princípio do Menor Privilégio (PoLP)

- **Analista:** SELECT nas tabelas Gold apenas
- **Data Engineer:** MODIFY em Silver/Bronze, SELECT em Gold
- **Admin:** Acesso irrestrito (documentado)

```sql
-- Revisar permissões excedentes mensalmente
SELECT
  principal,
  object_name,
  object_type,
  permission
FROM system.access.permissioning
WHERE permission NOT IN ('USAGE', 'SELECT')
ORDER BY principal;
```

### 3. Revogar Acesso em até 24h de Offboarding

```sql
-- Script de offboarding automático
REVOKE ALL PRIVILEGES ON CATALOG gold_catalog FROM GROUP 'team-departed@empresa.com.br';
REVOKE ROLE analyst_br FROM GROUP 'team-departed@empresa.com.br';
```

---

## Auditoria de Acessos

### Consultar Acesso Concedido

```sql
-- Quem tem SELECT na tabela de clientes?
SELECT
  principal,
  privilege,
  grant_time
FROM system.information_schema.effective_privileges
WHERE object_catalog = 'gold_catalog'
  AND object_schema = 'customers'
  AND object_name = 'dim_cliente';
```

### Verificar Quem Acessou Qual Tabela

```sql
-- Últimos 7 dias: acessos a dados sensíveis
SELECT
  actor_email,
  object_id,
  action_type,
  event_time
FROM system.access.audit
WHERE event_date >= CURRENT_DATE() - 7
  AND object_id LIKE '%fact_vendas%'
ORDER BY event_time DESC;
```

---

## Gotchas e Best Practices

| Gotcha                              | Solução                                            |
|-------------------------------------|--------------------------------------------------|
| Permissões herdam de Catalog → Schema | Conceder USAGE no Catalog = acesso a todos Schema |
| GRANT sem USAGE = sem efeito        | Sempre: GRANT USAGE FIRST, depois GRANT SELECT   |
| Revogar tabela não remove schema    | Revogar Schema não remove Catalog (hierarquia)   |
| Atraso em propagação AAD            | Permitir até 2h para permissões em novo usuário  |
