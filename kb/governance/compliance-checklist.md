# Compliance Checklist — LGPD e GDPR

**Último update:** 2026-04-09
**Domínio:** Conformidade regulatória, proteção de dados pessoais
**Escopo:** Lei Geral de Proteção de Dados (LGPD) Brasil + GDPR Europa

---

## Checklist de Conformidade

### 1. Data Mapping — Inventário de Dados Pessoais

| Item                      | Status | Evidência                                    | Revisor      |
|---------------------------|--------|----------------------------------------------|--------------|
| Catalogar todas as fontes | ⬜ OK  | Arquivo de mapping em `PERSONAL_DATA_MAP.md` | DPO          |
| Identificar PII em bruto  | ⬜ OK  | Query: `SELECT * FROM bronze_*` → CPF found | DataGov      |
| Marcar colunas PII        | ⬜ OK  | Tags em Unity Catalog aplicadas             | DataEng      |
| Documentar destinos       | ⬜ OK  | Tabelas Gold com PII identificadas          | DPO          |

**Template:**
```markdown
# Personal Data Mapping

## Fonte: SAP ERP (bronze_catalog.erp_customers_raw)
- **Proprietário:** SAP Team
- **Dados Pessoais:** nome, cpf, email, telefone, endereco, data_nascimento
- **Frequência:** Diária (00:00 UTC)
- **Destino:** silver_crm.customers → gold_catalog.sales.dim_cliente
- **Processamento:** Limpeza, deduplicação, mascaramento
```

---

### 2. Legal Basis — Base Legal para Processamento

| Base Legal     | Descrição                                              | Aplicação              |
|----------------|--------------------------------------------------------|------------------------|
| **Consentimento** | Usuário optou-in explicitamente (cookie banner, etc) | Marketing, Analytics   |
| **Contrato**   | Dados necessários para executar serviço contratado    | Cobrança, Envios      |
| **Obrigação Legal** | Lei exige coleta/processamento (fiscal, compliance) | Nota Fiscal, DGI      |
| **Interesse Legítimo** | Empresa tem interesse legítimo e sopesado (fraud)   | Detecção de fraude    |
| **Proteção da Vida** | Vida/saúde em risco (emergência)                     | Casos extremos        |

**Documentar por tabela:**
```sql
ALTER TABLE gold_catalog.customers.dim_cliente
SET TBLPROPERTIES (
  'legal_basis' = 'Contrato de Serviço',
  'legal_basis_description' = 'Dados necessários para entregar serviço ao cliente',
  'data_controller' = 'empresa@empresa.com.br',
  'dpia_required' = 'true',
  'dpia_status' = 'approved_2026_01_15'
);
```

---

### 3. Consent Management — Gestão de Consentimentos

| Campo                 | Descrição                                         | Checklist |
|-----------------------|---------------------------------------------------|-----------|
| **Consentimento**     | Usuário consentiu explicitamente (opt-in)        | ⬜ Docum. |
| **Data do Consentimento** | Timestamp quando consentimento foi dado          | ⬜ Log    |
| **Propósito**         | "Marketing", "Analytics", "Operacional"          | ⬜ Claro  |
| **Revogação**         | Caminho claro para revogar consentimento          | ⬜ UX OK  |
| **Auditoria**         | Log de todos os consentimentos/revogações        | ⬜ Audit  |

**Tabela de Consentimentos:**
```sql
CREATE TABLE gold_catalog.compliance.consents (
  id_consentimento STRING,
  id_cliente STRING,
  tipo_consentimento STRING,  -- 'marketing', 'analytics', 'operational'
  status STRING,  -- 'granted', 'revoked'
  data_consentimento TIMESTAMP,
  data_revogacao TIMESTAMP,
  ip_address STRING,  -- Para verificar legitimidade
  created_at TIMESTAMP
);

-- Consultar consentimentos válidos
SELECT id_cliente, tipo_consentimento
FROM gold_catalog.compliance.consents
WHERE status = 'granted'
  AND data_revogacao IS NULL
  AND tipo_consentimento = 'marketing';
```

---

### 4. Right to Erasure — Direito ao Esquecimento (SER Categoria 17)

**Processo Documentado:**

```sql
-- 1. Receber pedido de APAGAMENTO
-- E-mail: usuario@example.com quer ser esquecido

-- 2. Validar identidade (importante: verificar que realmente é o usuário)
-- Validação: responder de email registrado, token, etc.

-- 3. Identificar registros em TODAS as tabelas
DECLARE @email_to_erase STRING = 'usuario@example.com';

SELECT
  table_catalog,
  table_schema,
  table_name,
  COUNT(*) AS records_found
FROM (
  SELECT * FROM gold_catalog.customers.dim_cliente WHERE pii_email = @email_to_erase
  UNION ALL
  SELECT * FROM silver_crm.customers WHERE email = @email_to_erase
  UNION ALL
  SELECT * FROM bronze_catalog.erp_customers_raw WHERE email = @email_to_erase
)
GROUP BY table_catalog, table_schema, table_name;

-- 4. Deletar em ordem reversa de linhagem (Gold → Silver → Bronze)
DELETE FROM gold_catalog.sales.fact_vendas
WHERE id_cliente IN (
  SELECT id_cliente FROM gold_catalog.customers.dim_cliente
  WHERE pii_email = @email_to_erase
);

DELETE FROM gold_catalog.customers.dim_cliente
WHERE pii_email = @email_to_erase;

DELETE FROM silver_crm.customers
WHERE email = @email_to_erase;

DELETE FROM bronze_catalog.erp_customers_raw
WHERE email = @email_to_erase;

-- 5. Auditar a deleção
INSERT INTO gold_catalog.compliance.deletion_log
  (email_deleted, tables_affected, deletion_timestamp, reason)
VALUES
  (@email_to_erase, 'dim_cliente, fact_vendas, customers (silver), erp_customers_raw',
   CURRENT_TIMESTAMP(), 'Right to Erasure Request');

-- 6. Confirmar ao usuário (em até 30 dias)
-- E-mail: "Seu pedido foi processado em 2026-04-09 14:30:00. Todos seus dados foram apagados."
```

**SLA:** Até 30 dias (LGPD Art. 18) / 45 dias (GDPR Art. 12)

---

### 5. Data Retention — Política de Retenção de Dados

| Tabela                | Tipo de Dado | Retenção | Ação Após TTL | Responsável |
|-----------------------|--------------|----------|---------------|-------------|
| dim_cliente           | PII          | 5 anos   | Mascarar → Archive | DataGov   |
| fact_vendas           | Transacional  | 7 anos   | Arquivar      | Finance    |
| audit_log             | Auditoria    | 3 anos   | Arquivo       | Compliance |
| consent_log           | Consentimento | 2 anos   | Mascarar      | Legal      |

**Implementar TTL via Databricks:**

```sql
CREATE TABLE gold_catalog.sales.fact_vendas (
  id_transacao BIGINT,
  id_cliente BIGINT,
  valor_total DECIMAL(10, 2),
  data_transacao DATE,
  _ttl DATE DEFAULT CURRENT_DATE() + INTERVAL 7 YEAR
)
USING DELTA
TBLPROPERTIES (
  'retention_days' = '2555',  -- 7 anos
  'delta.enableDeletionVectors' = 'true'
);

-- Executar diariamente (jobcluster): deletar expirados
DELETE FROM gold_catalog.sales.fact_vendas
WHERE _ttl < CURRENT_DATE();
```

---

### 6. Masking em Não-Produção

**Regra:** Toda tabela com PII deve ser mascarada em DEV/STAGING.

```sql
-- Workspace: DEV
CREATE SCHEMA IF NOT EXISTS dev_catalog.customers;

-- View mascarada (consumida por devs)
CREATE VIEW dev_catalog.customers.dim_cliente_safe AS
SELECT
  id_cliente,
  -- Mascarar PII
  CONCAT('NOME_', MOD(id_cliente, 10000)) AS nome,
  CONCAT('***.**.**-', RIGHT(CAST(HASH(pii_cpf) AS STRING), 2)) AS cpf,
  CONCAT('dev-', id_cliente, '@masked.local') AS email,
  CONCAT('+55 (', MOD(id_cliente, 99), ') ****-****') AS telefone,
  regiao
FROM gold_catalog.customers.dim_cliente;

-- Bloquear acesso à tabela original
REVOKE SELECT ON TABLE gold_catalog.customers.dim_cliente
  FROM GROUP 'dev-team@empresa.com.br';

GRANT SELECT ON VIEW dev_catalog.customers.dim_cliente_safe
  TO GROUP 'dev-team@empresa.com.br';
```

---

### 7. Data Protection Impact Assessment (DPIA)

**Obrigatório para:** Processamento em larga escala, dados sensíveis, decisões automatizadas.

```markdown
# DPIA: Data Classification Project

## 1. Descrição do Processamento
- **Objetivo:** Classificar automaticamente todas as colunas como PII/Confidencial/Público
- **Dados:** 2.3M de registros em 145 tabelas Gold
- **Tecnologia:** ML Model (scikit-learn)
- **Impacto:** Nível alto (todos os dados da empresa)

## 2. Necessidade e Proporcionalidade
✅ Necessário: Conformidade LGPD, melhor governança
✅ Proporcional: Benefício > Risco

## 3. Riscos Identificados
- **Vazamento de Classificação:** Modelo expõe padrão de PII
  - Mitigação: Modelo treinado apenas em dados de teste
- **Falsos Negativos:** Modelo não identifica PII
  - Mitigação: Revisão manual de 5% amostra, retraining mensal

## 4. Direitos dos Sujeitos
- Acesso: Usuário pode pedir seus dados e classificação
- Retificação: Se classificação errada, pode corrigir
- Exclusão: Right to Erasure implementado

## 5. Aprovação
- Aprovado por: DPO (Data Protection Officer)
- Data: 2026-01-15
- Vigência: Até 2027-01-15 (revisão anual)
```

---

### 8. Breach Notification Process — Processo de Notificação de Incidente

**Descoberta → Análise → Notificação (em até 72h para GDPR)**

```sql
-- Tabela para registrar incidentes
CREATE TABLE gold_catalog.compliance.breach_log (
  incident_id STRING,
  discovery_date TIMESTAMP,
  breach_description STRING,
  affected_records INT,
  affected_data_types STRING,  -- 'cpf', 'email', 'senha', etc
  breach_source STRING,  -- 'SQL Injection', 'Unauthorized Access', etc
  severity STRING,  -- 'low', 'medium', 'high', 'critical'
  notification_sent BOOLEAN,
  notification_date TIMESTAMP,
  authorities_notified BOOLEAN,
  users_notified BOOLEAN,
  remediation_steps STRING,
  closed_date TIMESTAMP
);

-- Exemplo: detectar acesso anômalo (automático via auditoria)
INSERT INTO gold_catalog.compliance.breach_log
SELECT
  CONCAT('INC-', CURRENT_TIMESTAMP()),
  CURRENT_TIMESTAMP(),
  'Acesso fora de horário a dim_cliente por usuário técnico',
  (SELECT COUNT(*) FROM gold_catalog.customers.dim_cliente),
  'cpf, email, telefone',
  'Suspicious Activity',
  'high',  -- Requer investigação
  FALSE,
  NULL,
  FALSE,
  FALSE,
  'Investigar logs, revogar acesso se necessário, comunicar usuário',
  NULL;

-- Checklist: notificar dentro de 72h
SELECT
  incident_id,
  discovery_date,
  DATEDIFF(HOUR, discovery_date, CURRENT_TIMESTAMP()) AS horas_desde_descoberta,
  CASE
    WHEN DATEDIFF(HOUR, discovery_date, CURRENT_TIMESTAMP()) > 72
      THEN '🚨 VENCIDO'
    ELSE '⏳ VÁLIDO'
  END AS status_notificacao
FROM gold_catalog.compliance.breach_log
WHERE closed_date IS NULL
  AND severity IN ('high', 'critical');
```

---

## Cronograma Recomendado

| Frequência      | Atividade                           | Responsável       |
|-----------------|-------------------------------------|-------------------|
| **Mensal**      | Revisão de consentimentos revogados | Compliance        |
| **Mensal**      | Auditoria de acessos a PII          | DataGovernance    |
| **Trimestral**  | DPIA Review (conforme necessário)   | DPO + Tech Team   |
| **Trimestral**  | Relatório de conformidade LGPD      | Legal/Compliance  |
| **Anual**       | Auditoria externa de segurança      | Auditoria Externa |

---

## Status de Conformidade — Template

```markdown
# Status Conformidade Q2 2026

| Item                            | Status | Data Última Revisão | Observações        |
|---------------------------------|--------|--------------------|--------------------|
| Data Mapping                    | ✅ OK  | 2026-04-01         | Atualizado         |
| Legal Basis Documentado         | ✅ OK  | 2026-03-15         | Todas tabelas OK   |
| Consent Management              | ⚠️ WARN | 2026-04-05         | 3 consentimentos pendentes |
| Right to Erasure               | ✅ OK  | 2026-04-08         | 0 pedidos vencidos |
| Data Retention Policy          | ✅ OK  | 2026-02-01         | Review em Ago 2026 |
| Masking em DEV                 | ✅ OK  | 2026-04-09         | 100% mascarado     |
| DPIA Current                   | ✅ OK  | 2026-01-15         | Válido até Jan 2027|
| Breach Notification Ready      | ✅ OK  | 2026-04-01         | SOP documentado    |

**Status Geral: ✅ CONFORME**

**Próxima Auditoria:** 2026-07-01 (Trimestral)
```
