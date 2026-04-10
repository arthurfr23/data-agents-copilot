# DDL Patterns — Data Definition Language para Delta Tables

**Último update:** 2026-04-09
**Domínio:** CREATE TABLE, CREATE SCHEMA, ALTER TABLE, volumes
**Plataformas:** Databricks, Azure Fabric

---

## CREATE TABLE — Definição de Tabelas Delta

### Tabela Gerenciada (Managed)

```sql
CREATE TABLE gold_catalog.sales.fact_vendas (
  id_venda BIGINT NOT NULL COMMENT 'Chave primária',
  id_cliente BIGINT NOT NULL COMMENT 'FK para dim_cliente',
  data_venda DATE NOT NULL COMMENT 'Data da transação',
  valor DECIMAL(10, 2) NOT NULL COMMENT 'Valor em reais (R$)',
  quantidade INT COMMENT 'Quantidade de itens',
  desconto DECIMAL(4, 2) COMMENT 'Desconto em %',
  status VARCHAR(20) COMMENT 'Enum: ativa|cancelada|pendente',
  criado_em TIMESTAMP NOT NULL COMMENT 'Data de criação',
  atualizado_em TIMESTAMP COMMENT 'Data de atualização'
)
USING DELTA
COMMENT 'Fatos de vendas - Camada Gold'
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.enableDeletionVectors' = 'true'
);
```

### Tabela Externa (External)

```sql
-- Dados armazenados fora do warehouse (S3, ADLS)
CREATE TABLE gold_catalog.sales.fact_vendas_external (
  id_venda BIGINT,
  id_cliente BIGINT,
  data_venda DATE
)
USING DELTA
LOCATION 's3://my-bucket/gold/sales/fact_vendas';
-- Ao deletar tabela, dados em s3:// NÃO são removidos
```

**Diferença:**

| Tipo      | Armazenamento           | DELETE Tabela | Use Case                 |
|-----------|------------------------|---------------|------------------------|
| Managed   | /user/hive/warehouse/  | Delete dados  | Padrão (warehouse)      |
| External  | S3/ADLS location       | Keep dados    | Dados compartilhados    |

---

## Convenções de Nomenclatura

### Padrão Obrigatório: snake_case

```sql
-- ✅ CORRETO
CREATE TABLE gold_catalog.sales.fact_vendas (
  id_venda BIGINT,
  data_venda DATE,
  valor_total DECIMAL(10, 2)
);

-- ❌ ERRADO
CREATE TABLE gold_catalog.sales.FactVendas (  -- CamelCase
  idVenda BIGINT,  -- camelCase
  dataVenda DATE
);
```

### Prefixos Obrigatórios

| Prefixo  | Tipo                      | Exemplo                          |
|----------|---------------------------|--------------------------------|
| `bronze_` | Raw (Bronze)             | `bronze_erp_clientes_raw`       |
| `silver_` | Transformado (Silver)    | `silver_crm_clientes_clean`     |
| `gold_`  | Agregado/Star Schema    | `gold_vendas.fact_vendas`      |
| `dim_`   | Dimensão                | `dim_cliente`, `dim_data`       |
| `fact_`  | Fato                    | `fact_vendas`, `fact_eventos`   |

---

## Data Types — Tipos de Dados Recomendados

| Tipo Delta    | Uso                                    | Exemplo                    |
|---------------|----------------------------------------|---------------------------|
| BIGINT        | Inteiro grande (IDs, counts)          | `id_cliente BIGINT`       |
| INT           | Inteiro pequeno (flags, dias)         | `num_dias INT`            |
| DECIMAL(p,s)  | Valores monetários (precisão fixa)    | `valor DECIMAL(10, 2)`    |
| DOUBLE        | Floats científicos (menos preciso)    | `taxa_conversao DOUBLE`   |
| DATE          | Data apenas (YYYY-MM-DD)              | `data_venda DATE`         |
| TIMESTAMP     | Data + hora                           | `criado_em TIMESTAMP`     |
| VARCHAR(n)    | String com tamanho máximo            | `status VARCHAR(20)`      |
| STRING        | String ilimitado (recomendado)        | `descricao STRING`        |
| BOOLEAN       | Verdadeiro/Falso                     | `is_ativo BOOLEAN`        |
| ARRAY         | Lista de valores                      | `tags ARRAY<STRING>`      |
| MAP           | Chave-valor                          | `metadata MAP<STRING, STRING>` |

---

## CREATE SCHEMA — Definir Esquema

```sql
CREATE SCHEMA IF NOT EXISTS gold_catalog.sales
COMMENT 'Schemas com agregações finais para análise de vendas'
LOCATION '/user/hive/warehouse/gold_catalog.db/sales';
```

**Padrão por Workspace:**

```
gold_catalog
  └─ sales/        (fact_vendas, dim_cliente, dim_produto)
  └─ finance/      (fact_faturamento, dim_contas)
  └─ marketing/    (fact_eventos, dim_campanha)
  └─ governance/   (audit_log, compliance_checklist)
```

---

## ALTER TABLE — Modificar Estrutura

### Adicionar Coluna

```sql
-- Adicionar nova coluna
ALTER TABLE gold_catalog.sales.fact_vendas
ADD COLUMN margem_liquida DECIMAL(10, 2)
COMMENT 'Margem líquida da transação';

-- Com default
ALTER TABLE gold_catalog.sales.fact_vendas
ADD COLUMN versao_modelo INT DEFAULT 1
COMMENT 'Versão do modelo de precificação';
```

### Renomear Coluna

```sql
ALTER TABLE gold_catalog.sales.fact_vendas
RENAME COLUMN valor TO valor_bruto;
```

### Modificar Tipo de Dado

```sql
-- ❌ Cuidado: pode quebrar queries
ALTER TABLE gold_catalog.sales.fact_vendas
MODIFY COLUMN valor TYPE BIGINT;  -- Era DECIMAL, virou BIGINT
```

### Deletar Coluna

```sql
-- ✅ Moderno (Delta 2.0+)
ALTER TABLE gold_catalog.sales.fact_vendas
DROP COLUMN desconto;
```

---

## CREATE VOLUME — File Storage

Volumes são para armazenar arquivos (não SQL tables).

```sql
-- Criar volume
CREATE VOLUME IF NOT EXISTS gold_catalog.assets
COMMENT 'Armazena modelos ML, arquivos estáticos';

-- Usar em código
%fs ls /Volumes/gold_catalog/assets/

# Python
dbutils.fs.ls("/Volumes/gold_catalog/assets/")
```

**Casos de Uso:**
- Modelos de ML
- Configurações JSON/YAML
- Arquivos estáticos (imagens, PDFs)

---

## TBLPROPERTIES — Configurações de Tabela

### Propriedades Comuns

```sql
CREATE TABLE gold_catalog.sales.fact_vendas (...)
USING DELTA
TBLPROPERTIES (
  -- Delta Lake features
  'delta.enableChangeDataFeed' = 'true',       -- Habilitar CDF
  'delta.enableDeletionVectors' = 'true',      -- Soft delete eficiente

  -- Retenção e limpeza
  'delta.deletedFileRetentionDuration' = '30 days',

  -- Clustering
  'delta.liquid.clustering.enabled' = 'true',

  -- Compatibilidade
  'delta.columnMapping.mode' = 'name',  -- Suporta rename/drop

  -- Classificação
  'classification' = 'PII/Restrito',
  'data_owner' = 'analytics-team@empresa.com.br',
  'retention_days' = '1825'  -- 5 anos
);
```

---

## Exemplo Completo: Star Schema DDL

### Dimensão: dim_cliente

```sql
CREATE TABLE gold_catalog.sales.dim_cliente (
  id_cliente BIGINT NOT NULL COMMENT 'PK',
  pii_nome VARCHAR(255) NOT NULL COMMENT 'Nome completo (PII)',
  pii_cpf VARCHAR(14) COMMENT 'CPF (PII)',
  pii_email VARCHAR(100) COMMENT 'Email (PII)',
  data_cadastro DATE COMMENT 'Data de cadastro',
  status VARCHAR(20) COMMENT 'ativo|inativo',
  regiao VARCHAR(2) COMMENT 'UF (SP, RJ, MG, ...)',
  segmento VARCHAR(50) COMMENT 'Premium|Gold|Silver|Bronze',
  created_at TIMESTAMP COMMENT 'Data de criação',
  updated_at TIMESTAMP COMMENT 'Última atualização'
)
USING DELTA
COMMENT 'Dimensão de Clientes - Camada Gold'
TBLPROPERTIES (
  'classification' = 'PII/Restrito',
  'delta.enableChangeDataFeed' = 'true'
);

-- Índice lógico para acesso rápido
CREATE INDEX idx_cpf ON gold_catalog.sales.dim_cliente (pii_cpf);
```

### Fato: fact_vendas

```sql
CREATE TABLE gold_catalog.sales.fact_vendas (
  id_transacao BIGINT NOT NULL COMMENT 'PK',
  id_cliente BIGINT NOT NULL COMMENT 'FK',
  id_produto BIGINT NOT NULL COMMENT 'FK',
  id_data BIGINT NOT NULL COMMENT 'FK (dim_data)',
  data_venda DATE NOT NULL COMMENT 'Data agregação',

  -- Medidas
  quantidade INT NOT NULL COMMENT 'Qtd vendida',
  valor_unitario DECIMAL(10, 2) NOT NULL COMMENT 'Preço unitário (R$)',
  valor_total DECIMAL(12, 2) NOT NULL COMMENT 'Valor total = qtd x preço',
  desconto_pct DECIMAL(4, 2) COMMENT 'Desconto %',
  valor_liquido DECIMAL(12, 2) COMMENT 'Valor após desconto',

  -- Controle
  created_at TIMESTAMP NOT NULL COMMENT 'Data criação',
  updated_at TIMESTAMP COMMENT 'Data atualização'
)
USING DELTA
CLUSTERED BY (data_venda, id_cliente) INTO 256 BUCKETS
COMMENT 'Fatos de Vendas - Camada Gold'
TBLPROPERTIES (
  'classification' = 'Confidencial',
  'delta.enableChangeDataFeed' = 'true',
  'delta.enableDeletionVectors' = 'true',
  'retention_days' = '2555'  -- 7 anos (fiscal)
);
```

---

## Gotchas

| Gotcha                              | Solução                                     |
|-------------------------------------|--------------------------------------------|
| Modificar tipo de coluna = erro     | Droppepar coluna velha, criar nova         |
| LOCATION sem EXTERNAL = erro        | Sempre EXTERNAL ao apontar s3://           |
| TBLPROPERTIES case-sensitive        | Usar lowercase para propriedades padrão    |
| Rename coluna com índice            | Recriar índice após rename                 |
| Volume criado em raiz incorreta     | Usar /Volumes/catalog/schema/volume        |
