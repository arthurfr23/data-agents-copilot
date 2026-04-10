# DAX Best Practices — Padrões de Medidas e Cálculos

**Último update:** 2026-04-09
**Domínio:** DAX, medidas, contexto de filtro, performance
**Plataformas:** Power BI, Fabric Semantic Model

---

## CALCULATE — Modificação de Contexto de Filtro

### Padrão: Medida com CALCULATE

```dax
-- Medida padrão: soma com contexto de filtro atual
Total Sales = SUM(fact_vendas[valor])

-- Com CALCULATE: modificar contexto
Total Sales YTD =
  CALCULATE(
    SUM(fact_vendas[valor]),
    DATESBETWEEN(dim_data[data],
                 STARTOFYEAR(MAX(dim_data[data])),
                 MAX(dim_data[data]))
  )
```

### CALCULATE com FILTER — Contexto Explícito

```dax
-- Filtro explícito
Total Sales Premium =
  CALCULATE(
    SUM(fact_vendas[valor]),
    FILTER(dim_cliente, dim_cliente[segmento] = "Premium")
  )

-- Equivalente com ALL
Total Sales All Regions =
  CALCULATE(
    SUM(fact_vendas[valor]),
    ALL(dim_cliente[regiao])  -- Remove filtro de região
  )
```

---

## DIVIDE — Divisão Segura (Sem Erro)

### ❌ ERRADO: Divisão Simples

```dax
-- Risco: divisão por zero = erro #DIV/0!
Average Sale = SUM(fact_vendas[valor]) / COUNT(fact_vendas[id_fato])
```

### ✅ CORRETO: DIVIDE Function

```dax
-- DIVIDE: retorna 0 (ou valor default) em caso de divisão por zero
Average Sale =
  DIVIDE(
    SUM(fact_vendas[valor]),
    COUNT(fact_vendas[id_fato]),
    0  -- Valor default se denominador = 0
  )

-- Com percentual
Sales Percent =
  DIVIDE(
    [Total Sales],
    CALCULATE([Total Sales], ALL(dim_cliente)),
    0
  )
```

---

## SUMX / AVERAGEX — Iteração Linha-por-Linha

### Uso: Quando Precisa Iterar

```dax
-- Cálculo complexo que não cabe em função agregada simples
Margin Amount =
  SUMX(
    fact_vendas,
    (fact_vendas[valor_unitario] - fact_vendas[preco_custo]) * fact_vendas[quantidade]
  )

-- Média de vendas por cliente (requer iteração)
Avg Sales per Customer =
  AVERAGEX(
    VALUES(dim_cliente[sk_cliente]),  -- Iterar sobre clientes
    CALCULATE(SUM(fact_vendas[valor]))
  )
```

### Performance: SUMX vs Coluna Calculada

**SUMX em Medida:** Rápido (executa durante query).
**Coluna Calculada:** Lento (calcula toda linha na memória).

**Recomendação:** Usar SUMX em medida, não em coluna calculada.

---

## Time Intelligence — Funções de Data

### Comparação Período Anterior

```dax
-- Vendas do mês anterior
Sales Last Month =
  CALCULATE(
    [Total Sales],
    DATEADD(dim_data[data], -1, MONTH)
  )

-- Crescimento MoM
Sales Growth % =
  DIVIDE(
    [Total Sales] - [Sales Last Month],
    [Sales Last Month],
    0
  )
```

### Year-to-Date (YTD)

```dax
-- Soma acumulada desde início do ano
YTD Sales =
  CALCULATE(
    [Total Sales],
    DATESYTD(dim_data[data])
  )

-- Quarter-to-Date
QTD Sales =
  CALCULATE(
    [Total Sales],
    DATESQTD(dim_data[data])
  )
```

### Same Period Last Year

```dax
-- Comparação YoY
Sales SPLY =
  CALCULATE(
    [Total Sales],
    DATEADD(dim_data[data], -1, YEAR)
  )

-- YoY Growth
YoY Growth % =
  DIVIDE(
    [Total Sales] - [Sales SPLY],
    [Sales SPLY],
    0
  )
```

---

## Variables — VAR/RETURN para Legibilidade e Performance

### Anti-Pattern: Sem Variables

```dax
-- Difícil de ler, repeats cálculo
Profit Margin =
  DIVIDE(
    SUM(fact_vendas[valor]) - SUMX(fact_vendas, fact_vendas[preco_custo] * fact_vendas[quantidade]),
    SUM(fact_vendas[valor]),
    0
  )
```

### ✅ CORRETO: Variables

```dax
-- Legível, evita re-computação
Profit Margin =
  VAR TotalSales = SUM(fact_vendas[valor])
  VAR TotalCost = SUMX(fact_vendas, fact_vendas[preco_custo] * fact_vendas[quantidade])
  VAR Profit = TotalSales - TotalCost
  RETURN
    DIVIDE(Profit, TotalSales, 0)
```

**Benefícios:**
- Mais legível
- Evita re-computação (TotalSales calculado 1x)
- Debugging mais fácil

---

## FILTER vs Filtro em CALCULATE

### FILTER (Row by Row)

```dax
-- Iterar sobre tabela, testar condição
Total Sales Premium =
  SUMX(
    FILTER(fact_vendas,
           RELATED(dim_cliente[segmento]) = "Premium"),
    fact_vendas[valor]
  )
```

**Quando usar:** Condições complexas, necessidade de RELATED.

### Filtro Direto em CALCULATE

```dax
-- Aplicar filtro via contexto (mais rápido)
Total Sales Premium =
  CALCULATE(
    SUM(fact_vendas[valor]),
    dim_cliente[segmento] = "Premium"
  )
```

**Quando usar:** Filtros simples por coluna (mais rápido).

---

## ALL / ALLEXCEPT — Remover Filtros

### ALL() — Remove Todos os Filtros

```dax
-- Percentual do total geral (ignorar filtro de região)
Sales Pct of Grand Total =
  DIVIDE(
    [Total Sales],
    CALCULATE([Total Sales], ALL(dim_cliente)),  -- Remove ALL filtros de cliente
    0
  )
```

### ALLEXCEPT() — Remove Alguns Filtros

```dax
-- Percentual por categoria (ignorar regiões)
Sales Pct by Category =
  DIVIDE(
    [Total Sales],
    CALCULATE([Total Sales],
              ALLEXCEPT(dim_cliente, dim_cliente[categoria])),
    0
  )
```

---

## Format Strings — Formatação de Valores

### Padrão: Combinar com Número

```dax
Total Sales = SUM(fact_vendas[valor])
```

**Em Power BI:**
1. Selecionar medida
2. Tab "Modeling"
3. Format: `"R$ "#,##0.00"` (reais)

### Formato Dinâmico em DAX

```dax
-- Formatter números grandes (K, M, B)
Sales Formatted =
  IF(ABS([Total Sales]) >= 1000000,
     FORMAT([Total Sales] / 1000000, "0.0M"),
     IF(ABS([Total Sales]) >= 1000,
        FORMAT([Total Sales] / 1000, "0.0K"),
        FORMAT([Total Sales], "0")
     )
  )
```

---

## Measure Naming — Convenções

### Padrão Obrigatório

| Tipo              | Prefixo    | Exemplo                        |
|-------------------|------------|--------------------------------|
| **Sum**           | `Total *`  | `Total Sales`, `Total Quantity` |
| **Average**       | `Avg *`    | `Avg Sale`, `Avg Price`       |
| **Count**         | `Count *`  | `Count Orders`, `Count Clients` |
| **Percentage**    | `* %`      | `Sales %`, `Growth %`         |
| **Ratio**         | `* Ratio`  | `Profit Ratio`, `Conversion Ratio` |

### Display Names vs Field Names

```
Field name (no Power BI):  Total_Sales_USD
Display name (usuário vê): Total Sales (USD)
```

---

## Contexto de Filtro — Row vs Filter

### Row Context (Coluna Calculada)

```dax
-- Executado para cada linha
Profit per Unit = fact_vendas[valor_unitario] - fact_vendas[preco_custo]
-- Cálculo linha-por-linha (sem agregação)
```

### Filter Context (Medida)

```dax
-- Agregado com filtros aplicados
Total Profit =
  SUMX(fact_vendas,
       fact_vendas[valor_unitario] - fact_vendas[preco_custo])
-- Respeitando filtros de data, cliente, região
```

**Regra:** Preferir medidas (filter context) sobre colunas calculadas (row context).

---

## Performance — Boas Práticas

### 1. Evitar Colunas Calculadas

```dax
-- ❌ LENTO: Coluna calculada
Calculated Profit = fact_vendas[valor] - fact_vendas[custo]

-- ✅ RÁPIDO: Medida
Total Profit = SUMX(fact_vendas, fact_vendas[valor] - fact_vendas[custo])
```

### 2. Usar Variables para Re-use

```dax
-- ❌ Re-computa múltiplas vezes
Metric = [Total Sales] / [Total Sales Last Year] + [Total Sales] * 2

-- ✅ Computa 1x
Metric =
  VAR Sales = [Total Sales]
  RETURN Sales / [Total Sales Last Year] + Sales * 2
```

### 3. CALCULATE Aninhado com Cautela

```dax
-- ❌ Aninhamento profundo = lento
Measure =
  CALCULATE(
    [Total Sales],
    CALCULATE(
      FILTER(...),
      CALCULATE(...)
    )
  )

-- ✅ Simplificar
Measure =
  CALCULATE(
    [Total Sales],
    [Filtered Clients]  -- Sub-medida
  )
```

---

## Gotchas

| Gotcha                              | Solução                                     |
|-------------------------------------|--------------------------------------------|
| Divisão por zero (erro #DIV/0!)    | Usar DIVIDE() com default value            |
| SUMX em coluna calculada = lento   | Usar medida ao invés de coluna             |
| RELATED() retorna múltiplas valores| Usar VALUES() ou SUMMARIZE() antes        |
| Filter context não se aplica       | Verificar relacionamentos ativas           |
| Variables redeclaram contexto      | VAR dentro de CALCULATE cria novo contexto|
