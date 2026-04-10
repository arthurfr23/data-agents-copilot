# PII Classification — Classificação de Dados Pessoais Brasileiros

**Último update:** 2026-04-09
**Domínio:** Classificação de PII, conformidade LGPD, mascaramento
**Foco:** Dados brasileiros (CPF, CNPJ, email, telefone)

---

## Padrões de Identificação PII Brasileiros

| Tipo de Dado    | Padrão              | Exemplo              | Campo Típico        |
|-----------------|---------------------|----------------------|---------------------|
| **CPF**         | ###.###.###-##      | 123.456.789-10       | cpf, numero_cpf     |
| **CNPJ**        | ##.###.###/####-##  | 12.345.678/0001-90   | cnpj, numero_cnpj   |
| **Email**       | texto@dominio       | usuario@empresa.br   | email, email_contato |
| **Telefone**    | +55 (XX) XXXXX-XXXX | +55 (11) 98765-4321  | telefone, celular   |
| **Nome Completo** | [A-Za-záéíóú ]+     | João Silva Santos    | nome, nome_cliente  |
| **Data Nasc.**  | YYYY-MM-DD          | 1985-03-15           | data_nascimento     |
| **Endereço**    | Rua/Av + CEP        | Rua A, 123, SP 01234 | endereco, logradouro|

---

## Níveis de Classificação

### Classificação por Tabela

| Nível          | Descrição                                  | Controle de Acesso              | Mascaramento      |
|----------------|--------------------------------------------|---------------------------------|-------------------|
| **Público**    | Sem PII, sem restrição (tabelas ref)      | READ: todos                     | Nenhum            |
| **Interno**    | Dados operacionais sem PII sensível       | READ: time; MODIFY: próprio     | Nenhum            |
| **Confidencial** | Dados sensíveis (financeiro, estratégico) | READ: aprovado; MODIFY: restrição| Truncamento       |
| **PII/Restrito** | Dados pessoais identificáveis (LGPD)     | READ: aprovação formal; MODIFY: admin| Hash/Tokenização  |

### Exemplo de Classificação em Tabela

```sql
CREATE TABLE gold_catalog.customers.dim_cliente (
  id_cliente BIGINT COMMENT 'PK',
  nome VARCHAR COMMENT 'CLASSIFICACAO: PII/Restrito | Atributo identificador',
  cpf VARCHAR COMMENT 'CLASSIFICACAO: PII/Restrito | Número único',
  email VARCHAR COMMENT 'CLASSIFICACAO: PII/Restrito | Contato',
  telefone VARCHAR COMMENT 'CLASSIFICACAO: PII/Restrito | Contato',
  endereco VARCHAR COMMENT 'CLASSIFICACAO: Confidencial | Endereço residencial',
  data_nascimento DATE COMMENT 'CLASSIFICACAO: PII/Restrito | Dado biométrico',
  regiao VARCHAR COMMENT 'CLASSIFICACAO: Interno | Segmentação'
)
USING DELTA
COMMENT 'CLASSIFICACAO_TABELA: PII/Restrito | Dados pessoais de clientes brasileiros'
TBLPROPERTIES (
  'classification' = 'PII/Restrito',
  'lgpd_applicable' = 'true',
  'retention_days' = '1825'  -- 5 anos por LGPD
);
```

---

## Convenções de Nomenclatura para PII

### Prefixo `pii_` (Recomendado)

```sql
CREATE TABLE silver_crm.customers (
  id_cliente BIGINT,
  pii_nome VARCHAR,           -- Indica PII
  pii_cpf VARCHAR,
  pii_email VARCHAR,
  pii_telefone VARCHAR,
  pii_data_nascimento DATE,
  regiao VARCHAR              -- NÃO é PII
);
```

**Vantagem:** Ferramenta de auditoria pode automaticamente marcar colunas `pii_*` para mascaramento.

### Tags do Unity Catalog (Alternativa)

```sql
-- Criar tag de classificação
ALTER TABLE gold_catalog.customers.dim_cliente
  ALTER COLUMN nome SET TAGS ('pii_class' = 'cpf');

ALTER TABLE gold_catalog.customers.dim_cliente
  ALTER COLUMN cpf SET TAGS ('pii_class' = 'cpf', 'masking' = 'hash');
```

---

## Estratégias de Mascaramento

### 1. Hashing (Irreversível)

Para dados que precisam ser únicos mas não legíveis.

```sql
-- CPF → Hash SHA256
SELECT
  id_cliente,
  SHA2(pii_cpf, 256) AS cpf_hash,  -- Irreversível
  pii_email
FROM gold_catalog.customers.dim_cliente;
```

**Use para:** CPF, CNPJ, passaporte (quando precisa unicidade)
**Problema:** Hashes visíveis podem permitir rainbow table attack

### 2. Truncamento (Truncate)

Mostrar apenas últimos dígitos.

```sql
-- CPF: mostrar apenas últimos 2 dígitos
SELECT
  id_cliente,
  CONCAT('***.**.**-', RIGHT(pii_cpf, 2)) AS cpf_masked,
  LEFT(pii_email, 3) || '***' || RIGHT(pii_email, 8) AS email_masked
FROM gold_catalog.customers.dim_cliente;
```

**Use para:** Verificações visuais (CSR, atendimento)
**Vantagem:** Reconhecível, reversível apenas com acesso privilegiado

### 3. Tokenização (Hash com Salt)

Mapeamento consistente sem exposição de dado original.

```sql
-- Token consistente: mesmo CPF → mesmo token
SELECT
  id_cliente,
  CONCAT('TOKEN_', MD5(CONCAT(pii_cpf, 'salt_secreto'))) AS cpf_token,
  pii_email
FROM gold_catalog.customers.dim_cliente;
```

**Use para:** Desenvolvimento/testes, joins anônimos
**Vantagem:** Permitir correlação sem expor dados reais

### 4. Nulificação (Null)

Remove completamente PII.

```sql
-- Ambiente DEV: remover PII
SELECT
  id_cliente,
  NULL AS pii_cpf,
  NULL AS pii_nome,
  regiao
FROM gold_catalog.customers.dim_cliente;
```

**Use para:** Ambientes não-prod
**Risco:** Quebra queries que precisam desses dados

---

## Mascaramento por Ambiente

### Política: PII Sempre Mascarado em DEV/STAGING

```sql
-- View para DEV: mascarar automaticamente
CREATE VIEW dev_catalog.customers.dim_cliente_safe AS
SELECT
  id_cliente,
  CONCAT('NOME_', ROW_NUMBER() OVER (ORDER BY id_cliente)) AS pii_nome,  -- Dummy
  CONCAT('***.**.**-', RIGHT(pii_cpf, 2)) AS cpf_masked,
  CONCAT('user', id_cliente, '@masked.local') AS email_masked,
  CONCAT('+55 (', MOD(id_cliente, 99), ') ****-****') AS telefone_masked,
  regiao
FROM gold_catalog.customers.dim_cliente;

-- Alertar se alguém tentar acessar a tabela original em DEV
GRANT SELECT ON TABLE dev_catalog.customers.dim_cliente_safe TO GROUP 'dev-team@empresa.com.br';
REVOKE SELECT ON TABLE gold_catalog.customers.dim_cliente FROM GROUP 'dev-team@empresa.com.br';
```

---

## Unity Catalog Tags para Classificação Automática

```sql
-- 1. Criar tags de classificação
CREATE TAG 'pii_classification';
CREATE TAG 'masking_strategy';

-- 2. Aplicar a colunas PII
ALTER TABLE gold_catalog.customers.dim_cliente
  ALTER COLUMN pii_cpf
  SET TAGS ('pii_classification' = 'cpf', 'masking_strategy' = 'hash');

-- 3. Consultar tabelas com PII
SELECT
  table_catalog,
  table_schema,
  table_name,
  column_name,
  tags
FROM system.information_schema.columns
WHERE tags['pii_classification'] IS NOT NULL;
```

---

## Right to Erasure (Direito ao Esquecimento)

### Processo: Deletar Dados Pessoais

```sql
-- 1. Identificar registro a deletar (ex: CPF)
DECLARE @target_cpf STRING = '123.456.789-10';

-- 2. Encontrar todas as tabelas com esse CPF
SELECT
  table_catalog,
  table_schema,
  table_name,
  COUNT(*) AS registros_encontrados
FROM system.lineage.table_lineage tl
WHERE source_table LIKE '%customers%'
  OR target_table LIKE '%customers%'
GROUP BY 1, 2, 3;

-- 3. Deletar em ordem reversa de linhagem (Gold → Silver → Bronze)
DELETE FROM gold_catalog.sales.fact_vendas
WHERE id_cliente IN (
  SELECT id_cliente FROM gold_catalog.customers.dim_cliente
  WHERE pii_cpf = @target_cpf
);

DELETE FROM silver_crm.customers
WHERE pii_cpf = @target_cpf;

DELETE FROM bronze_catalog.erp_customers_raw
WHERE cpf = @target_cpf;

-- 4. Auditar
INSERT INTO audit_log.deletions (table_name, record_count, reason, timestamp)
VALUES ('dim_cliente', 1, 'Right to Erasure Request', CURRENT_TIMESTAMP());
```

---

## Gotchas e Riscos

| Risco                              | Mitigação                                    |
|------------------------------------|---------------------------------------------|
| Hashes visíveis permitindo ataque  | Usar SALT + HMAC, nunca SHA puro            |
| Truncamento reversível             | Armazenar salt separadamente (Key Vault)    |
| PII em logs de erro                | Não logar valores de coluna PII             |
| Backup legado com PII              | Mascarar backups, deletar após LGPD delete  |
| Visualização em desenvolvimento    | Usar VIEW mascarada, bloquear acesso direto |
