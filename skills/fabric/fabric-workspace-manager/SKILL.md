# SKILL: fabric-workspace-manager

> **Fonte:** Microsoft Fabric REST API (api.fabric.microsoft.com/v1)
> **Atualizado:** Abril 2026
> **Uso:** Leia este arquivo ANTES de gerenciar workspaces Fabric programaticamente via REST API.

---

## Overview

Gerencia workspaces Microsoft Fabric programaticamente -- lista, cria, atualiza, deleta e configura
atribuições de função (RBAC) e vinculação de capacidade via REST API.

### O Problema

Gerenciar workspaces Fabric manualmente no portal consome tempo e não escala para operações em lote.
Além disso, controlar permissões (Admin/Contributor/Member/Viewer) e vinculações de capacidade para múltiplos
usuários/grupos requer múltiplas chamadas REST e validação de estado.

### A Solucao

Esta skill encapsula operações de workspace completas:

- Listagem, criação, atualização e exclusão de workspaces
- Atribuições de função para Users, Groups, ServicePrincipals via RBAC
- Vinculação e desvinculação de capacidade (com polling para LRO)
- Resolução de workspaces por nome ou ID
- Validação e tratamento de erros nas respostas de status 202 (aceito) e 422 (conflito)

**Resultado:** Automação completa do ciclo de vida de workspaces sem chamar REST manualmente.

---

## Quick Start

Exemplo mais comum -- criar workspace e atribuir Admin a um usuário:

```python
from workspace_manager import create_workspace, add_workspace_role_assignment

# Criar workspace novo
ws = create_workspace(
    display_name="Analytics-2026",
    capacity="capacity-prod",
    description="Workspace para análise de vendas"
)
workspace_id = ws["id"]

# Atribuir Admin a usuário
add_workspace_role_assignment(
    workspace=workspace_id,
    user_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    user_type="User",
    role="Admin"
)
# Retorno: {"status": "success", "principal": {...}, "role": "Admin"}
```

---

## Common Patterns

### 1. `list_workspaces` -- Listar todos os workspaces

Leitura somente. Suporta paginação automática.

**Parametros:**

| Parametro | Tipo | Obrigatorio | Descricao |
|-----------|------|-------------|-----------|
| `df` | bool | Nao | Se True, retorna DataFrame; se False, lista de dicts |

**Fluxo interno:**
1. `GET /v1/workspaces` (com paginação)
2. Retorna lista de workspaces com campos: id, displayName, description, capacityId

**Exemplo:**

```python
from workspace_manager import list_workspaces

ws_list = list_workspaces(df=False)
for ws in ws_list:
    print(f"{ws['displayName']} | Capacity: {ws.get('capacityId', 'Nenhuma')}")
```

---

### 2. `create_workspace` -- Criar workspace novo

Cria workspace com nome, descrição e capacidade opcionais.

**Parametros:**

| Parametro      | Tipo   | Obrigatorio | Descricao                                   |
|----------------|--------|-------------|---------------------------------------------|
| `display_name` | str    | Sim         | Nome do workspace                           |
| `capacity`     | str    | Nao         | Nome ou ID da capacidade                    |
| `description`  | str    | Nao         | Descricao do workspace                      |

**Fluxo interno:**
1. Construir payload com displayName, capacityId (resolvido), description
2. `POST /v1/workspaces` com payload
3. Retorna detalhes do workspace criado (id, displayName, etc)

**Exemplo:**

```python
from workspace_manager import create_workspace

ws = create_workspace(
    display_name="Sales-Q2-2026",
    capacity="prod-capacity",
    description="Análise de vendas Q2"
)
print(f"Workspace criado: {ws['id']}")
```

---

### 3. `update_workspace` -- Atualizar propriedades

Atualiza nome e/ou descrição de um workspace existente.

**Parametros:**

| Parametro      | Tipo   | Obrigatorio | Descricao                      |
|----------------|--------|-------------|--------------------------------|
| `workspace`    | str    | Sim         | ID ou nome do workspace        |
| `display_name` | str    | Nao         | Novo nome                      |
| `description`  | str    | Nao         | Nova descricao                 |

**Fluxo interno:**
1. Resolver workspace para ID
2. `PATCH /v1/workspaces/{workspaceId}` com payload
3. Validar que pelo menos uma propriedade foi fornecida

**Exemplo:**

```python
from workspace_manager import update_workspace

update_workspace(
    workspace="Sales-Q2-2026",
    display_name="Sales-Q3-2026",
    description="Migrado para Q3"
)
```

---

### 4. `add_workspace_role_assignment` -- Atribuir funcao RBAC

Atribui papel (Admin/Contributor/Member/Viewer) a usuario/grupo/SPN em workspace.

**Parametros:**

| Parametro    | Tipo   | Obrigatorio | Descricao                                          |
|--------------|--------|-------------|-----------------------------------------------------|
| `workspace`  | str    | Sim         | ID ou nome do workspace                            |
| `user_uuid`  | str    | Sim         | ID do usuario/grupo/SPN                            |
| `user_type`  | str    | Nao         | User, Group, ServicePrincipal, ServicePrincipalProfile |
| `role`       | str    | Nao         | Admin, Contributor, Member, Viewer (padrao: Admin) |

**Fluxo interno:**
1. Validar user_type e role contra listas de valores permitidos
2. `POST /v1/workspaces/{workspaceId}/roleAssignments` com principal e role
3. Retorna detalhes da atribuicao

**Exemplo:**

```python
from workspace_manager import add_workspace_role_assignment

# Atribuir Contributor a um grupo
add_workspace_role_assignment(
    workspace="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    user_uuid="group-uuid-12345",
    user_type="Group",
    role="Contributor"
)

# Atribuir Viewer a SPN
add_workspace_role_assignment(
    workspace="Sales-Q2-2026",
    user_uuid="spn-uuid-67890",
    user_type="ServicePrincipal",
    role="Viewer"
)
```

---

### 5. `update_workspace_role_assignment` -- Atualizar papel

Muda o papel de um usuario/grupo/SPN em um workspace.

**Parametros:**

| Parametro   | Tipo | Obrigatorio | Descricao                  |
|-------------|------|-------------|----------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace    |
| `user_uuid` | str  | Sim         | ID do principal            |
| `role`      | str  | Nao         | Novo papel (default: Admin) |

**Fluxo interno:**
1. Resolver workspace para ID
2. Validar role
3. `PATCH /v1/workspaces/{workspaceId}/roleAssignments/{userUuid}` com payload role
4. Retorna atribuicao atualizada

**Exemplo:**

```python
from workspace_manager import update_workspace_role_assignment

# Promover de Member para Contributor
update_workspace_role_assignment(
    workspace="Sales-Q2-2026",
    user_uuid="user-uuid-999",
    role="Contributor"
)
```

---

### 6. `assign_to_capacity` e `unassign_from_capacity` -- Gerenciar capacidade

Vincula ou desvincula workspace de uma capacidade.

**Parametros (assign_to_capacity):**

| Parametro  | Tipo | Obrigatorio | Descricao               |
|-----------|------|-------------|-------------------------|
| `workspace` | str | Sim         | ID ou nome do workspace |
| `capacity`  | str | Sim         | ID ou nome da capacidade |

**Parametros (unassign_from_capacity):**

| Parametro  | Tipo | Obrigatorio | Descricao               |
|-----------|------|-------------|-------------------------|
| `workspace` | str | Sim         | ID ou nome do workspace |

**Fluxo interno:**
1. Resolver workspace e capacidade para IDs
2. `POST /v1/workspaces/{workspaceId}/assignToCapacity` ou `/unassignFromCapacity`
3. Aguardar status 202 (aceito)

**Exemplo:**

```python
from workspace_manager import assign_to_capacity, unassign_from_capacity

# Vincular workspace a capacidade
assign_to_capacity(
    workspace="Sales-Q2-2026",
    capacity="premium-capacity"
)

# Desvincullar de capacidade
unassign_from_capacity(
    workspace="Sales-Q2-2026"
)
```

---

## Reference Files

- [workspace-operations.md](workspace-operations.md) -- Referencia tecnica: endpoints REST, payloads, campos de resposta, exemplos cURL
- [role-assignments.md](role-assignments.md) -- Detalhes de RBAC: tipos de usuarios, papeis, matrix de permissoes

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **Workspace nao encontrado (404)** | Confirme workspace_id/name. Use `list_workspaces()` para validar. |
| **user_type invalido** | Use apenas: User, Group, ServicePrincipal, ServicePrincipalProfile. |
| **Role invalida** | Use apenas: Admin, Contributor, Member, Viewer. |
| **Capacidade nao encontrada** | Verifique que capacity existe via `list_capacities()`. |
| **Status 202 (LRO)** | Operacao de capacidade iniciada. O workspace sera vinculado em background; polling recomendado. |
| **Status 422 (Conflito)** | Workspace ja tem essa capacidade ou existe conflito de estado. Aguarde alguns segundos e retry. |
| **Token expirado (401)** | Renove token via Azure Identity. Nunca hardcode -- use Key Vault. |
| **Permissao insuficiente (403)** | Usuario autenticado nao tem permissao Admin no workspace para RBAC. |
