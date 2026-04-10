# Semantic Model Patterns — Modelagem Semântica Power BI/Fabric

**Último update:** 2026-04-09
**Domínio:** Modelos semânticos, relacionamentos, medidas
**Plataformas:** Power BI, Fabric Semantic Model

---

## Star Schema — Fundação Obrigatória

### Estrutura Padrão

```
┌─────────────────────────────────────────────┐
│          FACT TABLE (Fatos)                 │
│          fact_vendas                        │
│  ┌──────────────────────────────────────┐  │
│  │ id_fato (PK)                         │  │
│  │ sk_cliente (FK→dim_cliente)          │  │
│  │ sk_produto (FK→dim_produto)          │  │
│  │ sk_data (FK→dim_data)                │  │
│  │ MEASURES: quantidade, valor, desconto│  │
│  └──────────────────────────────────────┘  │
│         ↑                 ↑           ↑     │
├─────────┼─────────────────┼───────────┤    │
│ ┌───────┴──┐      ┌───────┴──┐  ┌───┴────┐│
│ │dim_cliente│      │dim_produto│ │dim_data││
│ │SK (PK)   │      │SK (PK)   │ │SK (PK) ││
│ │ nome     │      │ categoria│ │ data   ││
│ │ email    │      │ marca    │ │ ano    ││
│ │ regiao   │      │ preco    │ │ mes    ││
│ └──────────┘      └──────────┘ └────────┘│
└─────────────────────────────────────────────┘
```

### Regras Obrigatórias

1. **Fact tables** contêm apenas:
   - Foreign Keys (nunca visíveis ao usuário)
   - Measures (valores numéricos agregáveis)

2. **Dimension tables** contêm:
   - Surrogate Key (PK)
   - Natural Keys (nk_*)
   - Atributos descritivos

3. **Relationships** sempre Many-to-One:
   - Fact → Dimension
   - Nunca Many-to-Many (quebra contexto de filtro)

---

## Fact Tables — Medidas e Granularidade

### Estrutura Completa

```sql
-- No Fabric/Lakehouse (Gold layer)
CREATE TABLE gold_catalog.sales.fact_vendas (
  -- Surrogate Keys (nunca expor ao usuário final)
  sk_cliente BIGINT,
  sk_produto BIGINT,
  sk_data BIGINT,

  -- Degenerate Dimensions (atributos do fato)
  numero_nfe STRING,
  numero_pedido STRING,

  -- Measures (valores agregáveis)
  quantidade INT,
  valor_unitario DECIMAL(10, 2),
  valor_bruto DECIMAL(12, 2),
  desconto_reais DECIMAL(10, 2),
  valor_liquido DECIMAL(12, 2),

  -- Controle (nunca expor)
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  _is_deleted BOOLEAN
) USING DELTA;
```

### Granularidade: Nível de Detalhe

| Granularidade             | Exemplo                           | Uso                              |
|---------------------------|-----------------------------------|----------------------------------|
| **Transação**             | 1 linha por item de pedido         | Análise detalhada                |
| **Dia**                   | 1 linha por dia por cliente       | Análise diária                   |
| **Mês**                   | 1 linha por mês por região        | Relatório mensal                 |

**Recomendação:** Usar granularidade mais fina (transação) no Lakehouse; agregações em Semantic Model.

---

## Dimension Tables — Atributos Descritivos

### Dimensão: dim_cliente

```sql
CREATE TABLE gold_catalog.sales.dim_cliente (
  -- PK técnica (nunca expor)
  sk_cliente BIGINT PRIMARY KEY,

  -- Natural Key (referência de negócio)
  nk_cliente BIGINT,

  -- Atributos descritivos (expor no BI)
  cliente_nome STRING,
  cliente_email STRING,
  cliente_telefone STRING,
  cliente_regiao VARCHAR(2),  -- UF
  cliente_estado VARCHAR(20),
  cliente_segmento VARCHAR(20),  -- Premium/Gold/Silver/Bronze

  -- SCD2 (manter histórico)
  data_inicio TIMESTAMP,
  data_fim TIMESTAMP,
  is_ativo BOOLEAN,
  versao INT,

  -- Controle
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) USING DELTA;
```

### Dimensão: dim_produto

```sql
CREATE TABLE gold_catalog.sales.dim_produto (
  sk_produto BIGINT PRIMARY KEY,
  nk_produto STRING,  -- SKU

  -- Atributos (hierarquia de produto)
  produto_nome STRING,
  categoria STRING,           -- Nível 1
  subcategoria STRING,        -- Nível 2
  marca STRING,

  -- Atributos de preço
  preco_lista DECIMAL(10, 2),
  preco_custo DECIMAL(10, 2),
  margem_padrao DECIMAL(5, 2),

  -- SCD2
  data_inicio TIMESTAMP,
  data_fim TIMESTAMP,
  is_ativo BOOLEAN,

  created_at TIMESTAMP
) USING DELTA;
```

### Dimensão: dim_data

```sql
CREATE TABLE gold_catalog.shared.dim_data (
  sk_data BIGINT PRIMARY KEY,
  data DATE,

  -- Decomposição de data
  ano INT,
  trimestre INT,
  mes INT,
  semana INT,
  dia INT,

  -- Nome de periodo
  nome_mes VARCHAR(20),      -- Janeiro, Fevereiro, ...
  nome_mes_abr VARCHAR(3),   -- Jan, Fev, ...

  -- Flags (relativamente importante)
  is_fim_semana BOOLEAN,
  is_feriado BOOLEAN,
  nome_feriado VARCHAR(50),

  -- Padrão
  is_ativo BOOLEAN
) USING DELTA;
```

---

## Relationships — Muitos-para-Um Apenas

### ❌ ERRADO: Many-to-Many

```
dim_cliente (1) ←→ (Many) dim_produto
              ↓
         fact_vendas  (Many)
```

**Problema:** Filtrar por cliente não isola produtos únicos.

### ✅ CORRETO: Many-to-One Sempre

```
fact_vendas ← sk_cliente → dim_cliente
fact_vendas ← sk_produto → dim_produto
fact_vendas ← sk_data     → dim_data
```

**Configuração no Power BI:**

1. **Fact table:** fact_vendas
2. **Relationships:**
   - fact_vendas[sk_cliente] → dim_cliente[sk_cliente] (Many-to-One)
   - fact_vendas[sk_produto] → dim_produto[sk_produto] (Many-to-One)
   - fact_vendas[sk_data] → dim_data[sk_data] (Many-to-One)

3. **Cross-filter:** Ambos (um lado da relação filtra o outro)

---

## Role-Playing Dimensions — Múltiplos Relacionamentos

Quando uma dimensão se relaciona com fato de múltiplas formas.

### Exemplo: Datas Múltiplas

```sql
-- fact_vendas tem 3 colunas de data
CREATE TABLE gold_catalog.sales.fact_vendas (
  sk_data_venda BIGINT,      -- Data da transação
  sk_data_entrega BIGINT,    -- Data esperada entrega
  sk_data_faturamento BIGINT,-- Data do faturamento
  ...
);
```

### Solução: Renomear Dimensão

No Semantic Model, criar 3 cópias lógicas:
- `dim_data_venda` → Relacionar a sk_data_venda
- `dim_data_entrega` → Relacionar a sk_data_entrega
- `dim_data_faturamento` → Relacionar a sk_data_faturamento

Todas apontam para `dim_data` no Lakehouse, mas no BI:

```powerquery
// Em Power Query (Fabric)
Source = Sql.Database("..."),
dim_data = Source{[Item="dim_data"]},
dim_data_venda = dim_data,
dim_data_entrega = dim_data,
dim_data_faturamento = dim_data
```

---

## Slowly Changing Dimensions (SCD2) no Semantic Layer

### Problema: Múltiplas Versões

```
dim_cliente v1 (2020-2024): João Silva, SP
dim_cliente v2 (2024-2026): João Silva, RJ (mudou de estado)
```

### Solução: Filtrar Apenas Ativa

**Na Lakehouse:**
```sql
-- Marcar versão ativa
SELECT
  sk_cliente,
  cliente_nome,
  cliente_regiao,
  is_ativo  -- TRUE se versão ativa
FROM dim_cliente;
```

**No Semantic Model:**
```powerquery
// Filtrar apenas versão ativa (hidden measure)
let
  Source = Sql.Database("..."),
  DimCliente = Source{[Item="dim_cliente"]},
  FilteredActive = Table.SelectRows(DimCliente, each [is_ativo] = true)
in
  FilteredActive
```

---

## Hide Foreign Keys — Melhor UX

### ❌ ERRADO: FK Visíveis

```
fact_vendas:
  ├─ sk_cliente    ← Usuário vê (confuso)
  ├─ sk_produto    ← Usuário vê (confuso)
  ├─ quantidade
  └─ valor
```

### ✅ CORRETO: FK Ocultas

No Power BI:
1. Selecionar coluna `sk_cliente`
2. Tab "Modeling" → "Hidden"
3. Repeat para todas FKs

**Resultado:**
```
fact_vendas:
  ├─ quantidade
  ├─ valor
  └─ [SK columns hidden]

dim_cliente:
  ├─ cliente_nome
  ├─ cliente_regiao
  └─ [SK hidden]
```

---

## Naming Conventions — Convenções de Nome

### Padrão Obrigatório

| Tipo                  | Padrão           | Exemplo                    |
|-----------------------|------------------|----------------------------|
| **Tabela Fato**       | `fact_*`        | `fact_vendas`, `fact_eventos` |
| **Tabela Dimensão**   | `dim_*`         | `dim_cliente`, `dim_produto` |
| **Coluna (Attribute)**| `tabela_atributo` | `cliente_nome`, `produto_categoria` |
| **Medida**            | `Total_*` ou `Avg_*` | `Total Vendas`, `Avg Desconto` |
| **PK Técnica**        | `sk_*` (hidden) | `sk_cliente` (hidden)      |
| **FK**                | `sk_*` (hidden) | `sk_cliente` (hidden)      |

### Naming no Semantic Model

**Display Names (o que usuário vê):**
```
Fact Vendas
├─ Total Sales = SUM(quantidade * valor_unitario)
├─ Avg Discount = AVG(desconto_pct)
└─ Num Transactions = COUNT(sk_cliente)

Dim Cliente
├─ Cliente Name = cliente_nome
├─ Cliente Region = cliente_regiao
└─ Cliente Segment = cliente_segmento
```

---

## Relacionamentos Activos vs Inativos

### Ativo (Filtros são aplicados)

```
dim_cliente[sk_cliente] ← (Active) ← fact_vendas[sk_cliente]
```

Filtrar por `cliente_regiao` filtra automaticamente `fact_vendas`.

### Inativo (Precisa USERELATIONSHIP)

```
dim_cliente[sk_cliente] ← (Inactive) ← fact_vendas[sk_data_entrega]
```

Usar medida com:
```dax
Total Vendas (por data entrega) =
  CALCULATE(
    [Total Sales],
    USERELATIONSHIP(fact_vendas[sk_data_entrega], dim_data[sk_data])
  )
```

---

## Gotchas

| Gotcha                              | Solução                                   |
|-------------------------------------|--------------------------------------------|
| FK visível confunde usuário         | Marcar como Hidden no Power BI            |
| Many-to-Many relationship           | Criar tabela bridge em Lakehouse          |
| Múltiplas datas na fact            | Role-playing dimensions (copiar dim_data)|
| SCD2 retorna múltiplas versões     | Filtrar is_ativo=TRUE no Semantic Model |
| Relacionamento bidirecional         | Usar USERELATIONSHIP em medidas DAX      |
