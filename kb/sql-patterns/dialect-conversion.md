# Dialect Conversion — Spark SQL, T-SQL, KQL

**Último update:** 2026-04-09
**Domínio:** Conversão entre dialetos SQL
**Plataformas:** Databricks (Spark SQL), Fabric Warehouse (T-SQL), Fabric Eventhouse (KQL)

---

## Mapeamento de Plataformas

| Plataforma                    | Dialeto   | Engine              | Uso                           |
|-------------------------------|-----------|---------------------|-------------------------------|
| **Databricks Lakehouse**       | Spark SQL | Apache Spark        | Data lake, pipelines, ML      |
| **Azure Fabric Lakehouse**     | T-SQL     | SQL Synapse         | Data warehouse (SQL)          |
| **Azure Fabric Eventhouse**    | KQL       | Kusto Query Eng.    | Time-series, logs, eventos    |

---

## Date Functions — Operações com Datas

### Spark SQL vs T-SQL vs KQL

| Operação                  | Spark SQL                        | T-SQL                          | KQL                           |
|---------------------------|----------------------------------|--------------------------------|-------------------------------|
| **Data Atual**            | `CURRENT_DATE()`                 | `CAST(GETDATE() AS DATE)`      | `now()`                       |
| **Timestamp Atual**       | `CURRENT_TIMESTAMP()`            | `GETDATE()`                    | `now()`                       |
| **Adicionar Dias**        | `DATE_ADD(date, 7)`              | `DATEADD(DAY, 7, date)`        | `now() + 7d`                  |
| **Subtrair Dias**         | `DATE_SUB(date, 7)`              | `DATEADD(DAY, -7, date)`       | `now() - 7d`                  |
| **Diferença entre Datas** | `DATEDIFF(DAY, date1, date2)`    | `DATEDIFF(DAY, date1, date2)`  | `datetime_diff('day', date1, date2)` |
| **Extrair Ano**           | `YEAR(date)`                     | `YEAR(date)`                   | `year(date)`                  |
| **Extrair Mês**           | `MONTH(date)`                    | `MONTH(date)`                  | `month(date)`                 |
| **Extrair Dia**           | `DAY(date)`                      | `DAY(date)`                    | `day(date)`                   |

### Exemplos Práticos

#### Spark SQL
```sql
-- Últimas 30 dias
SELECT * FROM vendas
WHERE data_venda >= DATE_SUB(CURRENT_DATE(), 30);

-- Diferença em dias
SELECT DATEDIFF(DAY, '2026-01-01', '2026-04-09') AS dias_passados;
```

#### T-SQL
```sql
-- Últimas 30 dias
SELECT * FROM vendas
WHERE data_venda >= DATEADD(DAY, -30, CAST(GETDATE() AS DATE));

-- Diferença em dias
SELECT DATEDIFF(DAY, '2026-01-01', '2026-04-09') AS dias_passados;
```

#### KQL
```kusto
vendas
| where data_venda >= now(-30d)

// Diferença em dias
range dias from 0 to datediff('day', datetime('2026-01-01'), now())
| take 1
| extend dias_passados = dias
```

---

## String Functions — Operações de Texto

| Operação                  | Spark SQL              | T-SQL                  | KQL                      |
|---------------------------|------------------------|------------------------|--------------------------|
| **Concatenar**            | `CONCAT(s1, s2)`       | `CONCAT(s1, s2)`       | `strcat(s1, s2)`        |
| **Substring**             | `SUBSTRING(str, 1, 5)` | `SUBSTRING(str, 1, 5)` | `substring(str, 1, 5)`  |
| **Comprimento**           | `LENGTH(str)`          | `LEN(str)`             | `strlen(str)`           |
| **Uppercase**             | `UPPER(str)`           | `UPPER(str)`           | `toupper(str)`          |
| **Lowercase**             | `LOWER(str)`           | `LOWER(str)`           | `tolower(str)`          |
| **Trim**                  | `TRIM(str)`            | `TRIM(str)`            | `trim(str)`             |
| **Replace**               | `REPLACE(str, from, to)` | `REPLACE(str, from, to)` | `replace(str, from, to)` |
| **Split**                 | `SPLIT(str, delim)`    | `STRING_SPLIT(str, delim)` | `split(str, delim)` |

---

## Type Casting — Conversão de Tipos

| Conversão              | Spark SQL            | T-SQL                | KQL                    |
|------------------------|----------------------|----------------------|------------------------|
| **String → Int**       | `CAST(s AS INT)`     | `CAST(s AS INT)`     | `toint(s)`             |
| **String → Float**     | `CAST(s AS DOUBLE)` | `CAST(s AS FLOAT)`   | `todouble(s)`          |
| **String → Date**      | `CAST(s AS DATE)`    | `CAST(s AS DATE)`    | `todatetime(s)`        |
| **Int → String**       | `CAST(i AS STRING)` | `CAST(i AS VARCHAR)` | `tostring(i)`          |
| **Date → String**      | `DATE_FORMAT(d, 'yyyy-MM-dd')` | `CONVERT(VARCHAR, d, 23)` | `format_datetime('%Y-%m-%d', d)` |

### Exemplos

#### Spark SQL
```sql
SELECT
  CAST('123' AS INT) AS num,
  CAST(123.45 AS INT) AS truncado,
  CAST('2026-04-09' AS DATE) AS data;
```

#### T-SQL
```sql
SELECT
  CAST('123' AS INT) AS num,
  CAST(123.45 AS INT) AS truncado,
  CAST('2026-04-09' AS DATE) AS data;
```

#### KQL
```kusto
print
  num = toint('123'),
  truncado = toint(123.45),
  data = todatetime('2026-04-09');
```

---

## NULL Handling — Tratamento de Nulos

| Operação                  | Spark SQL             | T-SQL                 | KQL                   |
|---------------------------|----------------------|----------------------|------------------------|
| **Teste NULL**            | `col IS NULL`        | `col IS NULL`        | `isnull(col)`         |
| **Substituir NULL**       | `COALESCE(c1, c2, c3)` | `COALESCE(c1, c2, c3)` | `coalesce(c1, c2, c3)` |
| **IFNULL (2 args)**       | `IFNULL(col, default)` | `ISNULL(col, default)` | `iff(isnull(col), default, col)` |
| **NULLIF (retorna NULL)** | `NULLIF(c1, c2)`     | `NULLIF(c1, c2)`     | `iff(c1 == c2, null, c1)` |

### Exemplos

#### Spark SQL
```sql
SELECT
  COALESCE(email, 'NO_EMAIL') AS email_clean,
  NULLIF(valor, 0) AS valor_or_null  -- NULL se valor=0
FROM clientes;
```

#### T-SQL
```sql
SELECT
  ISNULL(email, 'NO_EMAIL') AS email_clean,
  NULLIF(valor, 0) AS valor_or_null
FROM clientes;
```

#### KQL
```kusto
clientes
| project
  email_clean = iff(isnull(email), 'NO_EMAIL', email),
  valor_or_null = iff(valor == 0, null, valor);
```

---

## Aggregations — Funções de Agregação

| Função              | Spark SQL      | T-SQL          | KQL            |
|---------------------|----------------|----------------|----------------|
| **SUM**             | `SUM(col)`     | `SUM(col)`     | `sum(col)`     |
| **AVG**             | `AVG(col)`     | `AVG(col)`     | `avg(col)`     |
| **COUNT**           | `COUNT(*)`     | `COUNT(*)`     | `count()`      |
| **COUNT DISTINCT**  | `COUNT(DISTINCT col)` | `COUNT(DISTINCT col)` | `dcount(col)` |
| **MIN/MAX**         | `MIN/MAX(col)` | `MIN/MAX(col)` | `min/max(col)` |
| **GROUP_CONCAT**    | `COLLECT_LIST` | `STRING_AGG`   | `make_list`    |
| **STDDEV**          | `STDDEV(col)`  | `STDEV(col)`   | `stdev(col)`   |

### Exemplos

#### Spark SQL
```sql
SELECT
  regiao,
  SUM(valor) AS total,
  COUNT(*) AS num_vendas,
  AVG(valor) AS media,
  COLLECT_LIST(id_produto) AS produtos
FROM vendas
GROUP BY regiao;
```

#### T-SQL
```sql
SELECT
  regiao,
  SUM(valor) AS total,
  COUNT(*) AS num_vendas,
  AVG(valor) AS media,
  STRING_AGG(CAST(id_produto AS VARCHAR), ',') AS produtos
FROM vendas
GROUP BY regiao;
```

#### KQL
```kusto
vendas
| summarize
  total = sum(valor),
  num_vendas = count(),
  media = avg(valor),
  produtos = make_list(id_produto)
  by regiao;
```

---

## Window Functions — Funções Analíticas

| Operação              | Spark SQL                              | T-SQL                              | KQL                    |
|-----------------------|----------------------------------------|-----------------------------------|------------------------|
| **ROW_NUMBER**        | `ROW_NUMBER() OVER (ORDER BY col)`     | `ROW_NUMBER() OVER (ORDER BY col)` | Não suportado        |
| **RANK**              | `RANK() OVER (ORDER BY col)`           | `RANK() OVER (ORDER BY col)`       | Não suportado        |
| **LAG/LEAD**          | `LAG(col) OVER (ORDER BY date)`        | `LAG(col) OVER (ORDER BY date)`    | `prev/next`          |
| **FIRST_VALUE**       | `FIRST_VALUE(col) OVER (ORDER BY date)` | `FIRST_VALUE(col) OVER (ORDER BY date)` | Não suportado |
| **SUM (window)**      | `SUM(col) OVER (PARTITION BY cat)`     | `SUM(col) OVER (PARTITION BY cat)` | `sum(col) by cat` |

### Exemplos

#### Spark SQL
```sql
SELECT
  id_cliente,
  data_venda,
  valor,
  LAG(valor) OVER (PARTITION BY id_cliente ORDER BY data_venda) AS valor_anterior,
  SUM(valor) OVER (PARTITION BY id_cliente ORDER BY data_venda
                   ROWS BETWEEN 30 PRECEDING AND CURRENT ROW) AS soma_30dias
FROM vendas;
```

#### T-SQL
```sql
SELECT
  id_cliente,
  data_venda,
  valor,
  LAG(valor) OVER (PARTITION BY id_cliente ORDER BY data_venda) AS valor_anterior,
  SUM(valor) OVER (PARTITION BY id_cliente ORDER BY data_venda
                   ROWS BETWEEN 30 PRECEDING AND CURRENT ROW) AS soma_30dias
FROM vendas;
```

#### KQL
```kusto
vendas
| sort by id_cliente, data_venda
| extend
  valor_anterior = prev(valor, 1),
  soma_30dias = sum(valor) by id_cliente;
```

---

## Conditional Logic — Lógica Condicional

| Operação              | Spark SQL                  | T-SQL                      | KQL                        |
|-----------------------|---------------------------|---------------------------|----------------------------|
| **IF/CASE**           | `CASE WHEN ... THEN ... END` | `CASE WHEN ... THEN ... END` | `iff(condition, true_val, false_val)` |
| **IF com Múltiplas**  | `CASE WHEN ... WHEN ... END` | `CASE WHEN ... WHEN ... END` | `case(condition1, val1, condition2, val2, ...)` |

### Exemplos

#### Spark SQL
```sql
SELECT
  id_cliente,
  CASE
    WHEN valor > 1000 THEN 'Premium'
    WHEN valor > 500 THEN 'Gold'
    WHEN valor > 100 THEN 'Silver'
    ELSE 'Bronze'
  END AS segmento
FROM vendas;
```

#### T-SQL
```sql
SELECT
  id_cliente,
  CASE
    WHEN valor > 1000 THEN 'Premium'
    WHEN valor > 500 THEN 'Gold'
    WHEN valor > 100 THEN 'Silver'
    ELSE 'Bronze'
  END AS segmento
FROM vendas;
```

#### KQL
```kusto
vendas
| project
  id_cliente,
  segmento = case(
    valor > 1000, 'Premium',
    valor > 500, 'Gold',
    valor > 100, 'Silver',
    'Bronze'
  );
```

---

## Gotchas and Common Mistakes

| Gotcha                              | Spark SQL                          | T-SQL                              | KQL                              |
|-------------------------------------|------------------------------------|------------------------------------|----------------------------------|
| DATEDIFF(DAY, d1, d2)               | Spark: d2 - d1 (não d1 - d2)      | SQL: d2 - d1 (igual)              | KQL: usa datetime_diff           |
| NULL em comparação (NULL = 'X')     | Sempre FALSE (use IS NULL)        | Sempre FALSE (use IS NULL)        | Sempre FALSE (use isnull())      |
| Window functions                   | Suportadas                        | Suportadas                        | Limitadas (KQL != SQL window)    |
| COALESCE vs ISNULL                 | COALESCE mais portável            | ISNULL é SQL-específico           | Use coalesce()                   |
| Type casting implícito              | Avoid, sempre explícito (CAST)    | Avoid, sempre explícito (CAST)    | Avoid, sempre explícito (toint)  |

---

## Quick Reference — Cheat Sheet

```
┌─────────────────────────────────────────────────────────────┐
│ Operação                │ Spark SQL   │ T-SQL    │ KQL      │
├─────────────────────────┼─────────────┼──────────┼──────────┤
│ Data hoje               │ CURRENT_DATE│GETDATE() │ now()    │
│ Add 7 dias              │ DATE_ADD()  │DATEADD()│ now()+7d │
│ String concat           │ CONCAT()    │CONCAT() │strcat()  │
│ NULLs                   │ COALESCE()  │ISNULL()│coalesce()│
│ Condicional             │ CASE        │ CASE     │ iff()    │
│ Agregação distintos     │ COUNT(DIST.)│COUNT(D.)│dcount()  │
│ Window function         │ ROW_NUMBER()│ROW_NUM()│ X        │
│ Type casting            │ CAST()      │ CAST()   │ toint()  │
└─────────────────────────────────────────────────────────────┘
```
