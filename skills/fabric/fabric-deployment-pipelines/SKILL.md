# SKILL: fabric-deployment-pipelines

> **Fonte:** Microsoft Fabric REST API (api.fabric.microsoft.com/v1)
> **Atualizado:** Abril 2026
> **Uso:** Leia este arquivo ANTES de gerenciar pipelines de deploy Fabric via REST API.

---

## Overview

Gerencia pipelines de deployment (CI/CD dev->test->prod) programaticamente -- cria pipelines,
configura estagios, atribui workspaces, executa deploys e monitora operacoes via REST API com
suporte a LRO (Long Running Operation) polling.

### O Problema

Deploy manual de conteudo entre workspaces consome tempo, nao escala e introduz risco de erro humano.
Alem disso, cada deployment requer multiplas chamadas REST para inicializar operacao, fazer polling,
validar conflitos e monitorar progresso ate conclusao.

### A Solucao

Esta skill encapsula o ciclo completo de CI/CD:

- Criacao de pipelines com multiplos estagios (Dev, Test, Prod)
- Atribuicao de workspaces a estagios
- Deploy seletivo de items (todos ou selecionados)
- Polling automatico de LRO ate conclusao (sucesso/falha)
- Listagem de operacoes e detalhes
- Atribuicoes de papel para gerenciar acesso ao pipeline

**Resultado:** Deploy CI/CD completo em 1-2 chamadas encapsuladas (criar pipeline + deploy).

---

## Quick Start

Exemplo mais comum -- criar pipeline 3-estagios e fazer deploy de Dev para Test:

```python
from deployment_pipelines import create_deployment_pipeline, assign_workspace_to_stage, deploy_stage_content

# 1. Criar pipeline com 3 estagios
pipeline = create_deployment_pipeline(
    display_name="DataLake-Pipeline",
    stages=[
        {"displayName": "Development", "description": "Dev", "isPublic": False},
        {"displayName": "Testing", "description": "Test", "isPublic": False},
        {"displayName": "Production", "description": "Prod", "isPublic": True}
    ]
)
pipeline_id = pipeline["id"]

# 2. Atribuir workspaces
assign_workspace_to_stage(pipeline_id, "Development", "dev-workspace")
assign_workspace_to_stage(pipeline_id, "Testing", "test-workspace")
assign_workspace_to_stage(pipeline_id, "Production", "prod-workspace")

# 3. Fazer deploy com LRO polling
deploy_stage_content(
    pipeline=pipeline_id,
    source_stage="Development",
    target_stage="Testing",
    note="Deploy automatizado Q2-2026"
)
# Retorno: {"status": "success", "deploymentId": "...", "executionTime": "120s"}
```

---

## Common Patterns

### 1. `create_deployment_pipeline` -- Criar pipeline novo

Cria pipeline com nome, estagios e descricao opcionais.

**Parametros:**

| Parametro      | Tipo | Obrigatorio | Descricao                                          |
|----------------|------|-------------|-----------------------------------------------------|
| `display_name` | str  | Sim         | Nome do pipeline                                   |
| `stages`       | list | Sim         | Lista de dicts com displayName, description, isPublic |
| `description`  | str  | Nao         | Descricao do pipeline                              |

**Fluxo interno:**
1. Validar que stages nao esta vazio
2. `POST /v1/deploymentPipelines` com payload stages
3. Retorna detalhes do pipeline com IDs de estagios

**Exemplo:**

```python
from deployment_pipelines import create_deployment_pipeline

stages = [
    {"displayName": "Dev", "description": "Development", "isPublic": False},
    {"displayName": "Stage", "description": "Staging", "isPublic": False},
    {"displayName": "Prod", "description": "Production", "isPublic": True}
]

pipeline = create_deployment_pipeline(
    display_name="MyPipeline",
    stages=stages,
    description="3-stage CI/CD pipeline"
)
print(f"Pipeline criado: {pipeline['id']}")
```

---

### 2. `assign_workspace_to_stage` -- Vincular workspace a estagios

Atribui workspace a um estagios especifico do pipeline.

**Parametros:**

| Parametro  | Tipo | Obrigatorio | Descricao                      |
|------------|------|-------------|--------------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace        |
| `pipeline` | str  | Sim         | ID ou nome do pipeline         |
| `stage`    | str  | Sim         | Nome ou ID do estagios         |

**Fluxo interno:**
1. Resolver pipeline, estagios e workspace para IDs
2. `POST /v1/deploymentPipelines/{pipelineId}/stages/{stageId}/assignWorkspace`
3. Retorna detalhes do estagios atualizado

**Exemplo:**

```python
from deployment_pipelines import assign_workspace_to_stage

assign_workspace_to_stage(
    workspace="dev-analytics",
    pipeline="MyPipeline",
    stage="Dev"
)
```

---

### 3. `deploy_stage_content` -- Executar deploy com LRO polling

Faz deploy de conteudo de um estagios para outro com suporte a deploy seletivo.

**Parametros:**

| Parametro       | Tipo | Obrigatorio | Descricao                                      |
|-----------------|------|-------------|------------------------------------------------|
| `pipeline`      | str  | Sim         | ID ou nome do pipeline                         |
| `source_stage`  | str  | Sim         | Nome ou ID do estagios origem                  |
| `target_stage`  | str  | Sim         | Nome ou ID do estagios destino                 |
| `items`         | list | Nao         | Lista de items para deploy seletivo            |
| `note`          | str  | Nao         | Anotacao/comentario do deploy                  |
| `options`       | dict | Nao         | Opcoes adicionais (allowCrossRegionDeployment) |

**Fluxo interno:**
1. Resolver pipeline, estagios para IDs
2. Construir payload com sourceStageId, targetStageId, items (optional), note
3. `POST /v1/deploymentPipelines/{pipelineId}/deploy` com LRO support
4. Polling automatico ate status == "Succeeded" ou "Failed"
5. Retorna detalhes da operacao com tempo de execucao

**Exemplo - Deploy tudo:**

```python
from deployment_pipelines import deploy_stage_content

result = deploy_stage_content(
    pipeline="MyPipeline",
    source_stage="Dev",
    target_stage="Stage",
    note="Producao de semantico models"
)
```

**Exemplo - Deploy seletivo (items especificos):**

```python
from deployment_pipelines import deploy_stage_content

items = [
    {"sourceItemId": "model-uuid-1", "itemType": "SemanticModel"},
    {"sourceItemId": "report-uuid-2", "itemType": "Report"}
]

result = deploy_stage_content(
    pipeline="MyPipeline",
    source_stage="Dev",
    target_stage="Stage",
    items=items,
    note="Deploy seletivo de 2 items"
)
```

---

### 4. `list_deployment_pipeline_operations` -- Monitorar historico

Lista todas as operacoes (deploys) executadas em um pipeline.

**Parametros:**

| Parametro  | Tipo | Obrigatorio | Descricao          |
|------------|------|-------------|---------------------|
| `pipeline` | str  | Sim         | ID ou nome pipeline |

**Fluxo interno:**
1. Resolver pipeline para ID
2. `GET /v1/deploymentPipelines/{pipelineId}/operations` (com paginacao)
3. Retorna lista de operacoes com status, timestamp, itens deployados

**Exemplo:**

```python
from deployment_pipelines import list_deployment_pipeline_operations

ops = list_deployment_pipeline_operations(pipeline="MyPipeline")
for op in ops:
    print(f"{op['createdTime']} | {op['status']} | Items: {op['itemsCount']}")
```

---

### 5. `add_deployment_pipeline_role_assignment` -- RBAC pipeline

Atribui papel (Admin/Contributor/Member/Viewer) a usuario/grupo/SPN no pipeline.

**Parametros:**

| Parametro    | Tipo | Obrigatorio | Descricao                        |
|--------------|------|-------------|----------------------------------|
| `pipeline`   | str  | Sim         | ID ou nome do pipeline           |
| `user_uuid`  | str  | Sim         | ID do usuario/grupo/SPN          |
| `user_type`  | str  | Nao         | User, Group, ServicePrincipal... |
| `role`       | str  | Nao         | Admin, Contributor, Member, Viewer |

**Fluxo interno:**
1. Validar user_type e role
2. `POST /v1/deploymentPipelines/{pipelineId}/roleAssignments`
3. Retorna detalhes da atribuicao

**Exemplo:**

```python
from deployment_pipelines import add_deployment_pipeline_role_assignment

add_deployment_pipeline_role_assignment(
    pipeline="MyPipeline",
    user_uuid="devops-team-uuid",
    user_type="Group",
    role="Admin"
)
```

---

## Reference Files

- [deployment-operations.md](deployment-operations.md) -- Payloads REST, estrategias de conflito, opcoes de deployment, exemplos cURL

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **Pipeline nao encontrado (404)** | Confirme pipeline_id/name. Use `list_deployment_pipelines()`. |
| **Estagios nao encontrado (404)** | Verifique nome do estagios. Stage IDs sao gerados na criacao do pipeline. |
| **Workspace nao atribuido ao estagios** | Execute `assign_workspace_to_stage()` antes de deploy. |
| **Deploy falha com conflito (422)** | Item com mesmo nome existe no target stage. Use conflict resolution (PreferRemote/PreferWorkspace). |
| **LRO timeout** | Deploy grande pode demorar >120s. Aumente timeout para 300s ou implemente polling customizado. |
| **Status 202 (LRO iniciada)** | Deploy aceitado. Polling comeca automaticamente; aguarde ate conclusao. |
| **Permissao insuficiente (403)** | Usuario nao tem Admin no pipeline. Peca ao proprietario para atribuir papel. |
| **Token expirado (401)** | Renove token via MSAL. Configure Azure Identity ou Key Vault. |
