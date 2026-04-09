# SKILL: fabric-notebook-manager

> **Fonte:** Microsoft Fabric REST API (api.fabric.microsoft.com/v1)
> **Atualizado:** Abril 2026
> **Uso:** Leia este arquivo ANTES de manipular notebooks Fabric programaticamente via REST API.

---

## Overview

Gerencia notebooks Microsoft Fabric programaticamente -- adiciona, edita, remove e lista
celulas via REST API (`getDefinition` / `updateDefinition`).

### O Problema

Modificar um notebook Fabric programaticamente exige 4 chamadas REST separadas:

1. `getDefinition` -- ler estado atual do notebook (retorna payload base64)
2. Decodificar base64, parsear JSON .ipynb, modificar as celulas
3. `updateDefinition` -- enviar o notebook atualizado (inicia Long Running Operation)
4. `getDefinition` -- validar que a mudanca foi aplicada corretamente

Esse fluxo consome tokens do agente e introduz complexidade desnecessaria quando repetido
multiplas vezes numa sessao.

### A Solucao

Esta skill encapsula o ciclo completo `getDefinition -> modificar -> updateDefinition -> validar`
em operacoes atomicas reutilizaveis. Cada operacao cuida internamente de:

- Decodificacao/codificacao base64 do payload
- Parsing do formato Jupyter Notebook (.ipynb)
- Aguardar o LRO (Long Running Operation) ate conclusao
- Validacao pos-escrita via re-leitura do notebook

**Resultado:** de ~4 chamadas manuais para 1 operacao encapsulada por modificacao.

---

## Quick Start

Exemplo mais comum -- adicionar uma celula de codigo PySpark ao final de um notebook:

```python
from notebook_manager import add_cell

add_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    source="df = spark.read.table('bronze.bronze_orders')\ndisplay(df.limit(10))",
    cell_type="code",
    position=None  # None = adiciona ao final
)
# Retorno: {"status": "success", "total_cells": 8, "new_cell_index": 7}
```

---

## Common Patterns

### 1. `list_cells` -- Listar celulas do notebook

Leitura somente. Executa apenas `getDefinition` + decode (sem escrita).

**Parametros:**

| Parametro      | Tipo   | Obrigatorio | Descricao                          |
|----------------|--------|-------------|------------------------------------|
| `workspace_id` | str    | Sim         | ID do workspace Fabric             |
| `item_id`      | str    | Sim         | ID do notebook (ou notebook_name)  |

**Fluxo interno:**
1. `GET /v1/workspaces/{workspaceId}/items/{itemId}/getDefinition`
2. Decodifica `definition.parts[].payload` de base64 para JSON
3. Retorna lista de celulas com indice, tipo e preview do conteudo

**Exemplo:**

```python
from notebook_manager import get_notebook_cells

cells = get_notebook_cells(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555"
)

for i, cell in enumerate(cells):
    preview = cell["source"][:80] if cell["source"] else "(vazio)"
    print(f"[{i}] {cell['cell_type']:10s} | {preview}")

# Saida:
# [0] markdown   | # Pipeline Bronze -> Silver
# [1] code       | spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
# [2] code       | df = spark.read.table("bronze.bronze_orders")
# [3] code       | df_silver.write.format("delta").mode("overwrite")...
```

---

### 2. `add_cell` -- Adicionar celula(s)

Adiciona uma ou mais celulas ao notebook em posicao especifica ou ao final.

**Parametros:**

| Parametro      | Tipo       | Obrigatorio | Descricao                                            |
|----------------|------------|-------------|------------------------------------------------------|
| `workspace_id` | str        | Sim         | ID do workspace Fabric                               |
| `item_id`      | str        | Sim         | ID do notebook                                       |
| `source`       | str / list | Sim         | Codigo da celula (str) ou lista de linhas            |
| `cell_type`    | str        | Nao         | `"code"` (padrao) ou `"markdown"`                    |
| `position`     | int / None | Nao         | Indice de insercao. `None` = final do notebook       |

**Fluxo interno:**
1. `getDefinition` -- obter estado atual
2. Decodificar base64, parsear JSON .ipynb
3. Construir objeto de celula no formato Jupyter e inserir no array `cells`
4. Recodificar para base64, chamar `updateDefinition`
5. Aguardar LRO ate `status == "Succeeded"`
6. `getDefinition` -- validar que a celula foi adicionada

**Exemplo:**

```python
from notebook_manager import add_cell

# Adicionar celula markdown no inicio (posicao 0)
add_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    source="# Pipeline de Vendas\n\nProcessamento Bronze -> Silver -> Gold",
    cell_type="markdown",
    position=0
)

# Adicionar celula de codigo ao final
add_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    source="display(spark.sql('SELECT count(*) FROM gold.fato_vendas'))",
    cell_type="code"
)
```

---

### 3. `update_cell` -- Atualizar celula existente

Atualiza o conteudo de uma celula identificada pelo indice.

**Parametros:**

| Parametro      | Tipo       | Obrigatorio | Descricao                                   |
|----------------|------------|-------------|---------------------------------------------|
| `workspace_id` | str        | Sim         | ID do workspace Fabric                      |
| `item_id`      | str        | Sim         | ID do notebook                              |
| `cell_index`   | int        | Sim         | Indice da celula a atualizar (0-based)      |
| `new_source`   | str / list | Sim         | Novo conteudo da celula                     |

**Fluxo interno:**
1. `getDefinition` -- obter estado atual
2. Decodificar e validar que `cell_index` esta dentro do range
3. Substituir `cells[cell_index]["source"]` pelo novo conteudo
4. Recodificar e chamar `updateDefinition`
5. Aguardar LRO
6. `getDefinition` -- validar mudanca

**Exemplo:**

```python
from notebook_manager import update_cell

# Atualizar celula no indice 2 com nova query
update_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    cell_index=2,
    new_source="df = spark.sql('SELECT * FROM silver.silver_orders WHERE order_date >= \"2026-01-01\"')"
)
```

---

### 4. `delete_cell` -- Remover celula

Remove uma celula do notebook pelo indice.

**Parametros:**

| Parametro      | Tipo | Obrigatorio | Descricao                              |
|----------------|------|-------------|----------------------------------------|
| `workspace_id` | str  | Sim         | ID do workspace Fabric                 |
| `item_id`      | str  | Sim         | ID do notebook                         |
| `cell_index`   | int  | Sim         | Indice da celula a remover (0-based)   |

**Fluxo interno:**
1. `getDefinition` -- obter estado atual
2. Decodificar e validar que `cell_index` esta dentro do range
3. Remover `cells[cell_index]` do array
4. Recodificar e chamar `updateDefinition`
5. Aguardar LRO
6. `getDefinition` -- validar remocao

**Exemplo:**

```python
from notebook_manager import delete_cell

# Remover celula de debug no indice 4
delete_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    cell_index=4
)
# Retorno: {"status": "success", "total_cells": 6, "removed_index": 4}
```

---

### 5. `replace_notebook` -- Substituir conteudo completo

Substitui todas as celulas do notebook por um novo conjunto.

**Parametros:**

| Parametro      | Tipo | Obrigatorio | Descricao                                        |
|----------------|------|-------------|--------------------------------------------------|
| `workspace_id` | str  | Sim         | ID do workspace Fabric                           |
| `item_id`      | str  | Sim         | ID do notebook                                   |
| `cells`        | list | Sim         | Lista de dicts `{"source": ..., "cell_type": ...}` |

**Fluxo interno:**
1. `getDefinition` -- obter estado atual (preservar metadata do notebook)
2. Decodificar, substituir array `cells` inteiro mantendo `metadata` e `nbformat`
3. Recodificar e chamar `updateDefinition`
4. Aguardar LRO
5. `getDefinition` -- validar que o numero de celulas corresponde

**Exemplo:**

```python
from notebook_manager import replace_notebook_content

cells = [
    {"source": "# Notebook Gerado Automaticamente", "cell_type": "markdown"},
    {"source": "spark.conf.set('spark.sql.parquet.vorder.enabled', 'true')", "cell_type": "code"},
    {"source": "df = spark.read.table('bronze.bronze_vendas')\ndisplay(df.limit(5))", "cell_type": "code"}
]

replace_notebook_content(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    cells=cells
)
# Retorno: {"status": "success", "total_cells": 3}
```

---

## Reference Files

- [notebook-operations.md](notebook-operations.md) -- Referencia tecnica completa: estrutura JSON .ipynb, API REST, codigo Python, tratamento de erros
- [examples.md](examples.md) -- Exemplos praticos de uso em cenarios reais de pipeline Medallion

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **LRO retorna status "Failed"** | Verifique se o JSON .ipynb esta valido. Erros comuns: `source` como string ao inves de lista, `cell_type` invalido. Veja tratamento em [notebook-operations.md](notebook-operations.md). |
| **Notebook nao encontrado (404)** | Confirme `workspace_id` e `item_id`. Use `mcp__fabric__list_items` para buscar o ID correto do notebook. |
| **Indice fora do range** | Use `list_cells` antes de `update_cell` ou `delete_cell` para confirmar o numero de celulas existentes. |
| **Conflito de edicao concorrente (409)** | Outro usuario ou processo editou o notebook entre `getDefinition` e `updateDefinition`. Re-execute a operacao (retry automatico com backoff). |
| **Token expirado (401)** | Renove o Bearer token via Azure Identity / MSAL. Nunca hardcode tokens -- use Azure Key Vault ou Managed Identity. |
| **Timeout no LRO** | O padrao e 120 segundos de polling. Para notebooks grandes (>50 celulas), aumente o timeout para 300 segundos. |
