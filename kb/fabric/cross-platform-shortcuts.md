# KB: Shortcuts, Mirroring e Integração Cross-Platform

**Domínio:** Zero-copy data access, shortcuts, mirroring, deployment pipelines, Git e integração multi-cloud.
**Palavras-chave:** Shortcuts, Mirroring, ADLS Gen2, S3, Unity Catalog, Deployment Pipelines, Git.

---

## O que é Shortcut?

Shortcut é um **link lógico** para dados externos (sem cópia):

| Propriedade | Shortcut | Copy |
|------------|----------|------|
| **Storage** | Referência ao original | Cópia local |
| **Latência** | 1-5ms (rede) | Instantâneo (local) |
| **Custo** | Apenas query | Query + storage |
| **Update** | Real-time (source) | Manual resync |
| **Governance** | Controle fonte | Duplicado |

**Use case:** Lakehouse Gold referencia dados em Databricks Unity Catalog, ADLS, S3.

---

## Tipos de Shortcut Suportados

### OneLake (Cross-Workspace)

```http
POST /workspaces/{workspace-id}/items/{lakehouse-id}/shortcuts
{
  "path": "Tables",
  "name": "shared_dim_customer",
  "target": {
    "oneLake": {
      "itemId": "source-lakehouse-id",
      "path": "/Gold/CRM/dim_customer",
      "workspace_id": "source-workspace-id"
    }
  },
  "shortcutConflictPolicy": "Abort"
}
```

### ADLS Gen2 (Azure Data Lake)

```http
{
  "path": "Files/External",
  "name": "raw_data_adls",
  "target": {
    "adlsGen2": {
      "connectionId": "{connection-id}",
      "location": "mycontainer",
      "subpath": "/data/raw"
    }
  }
}
```

| Campo | Exemplo | Nota |
|-------|---------|------|
| **connectionId** | conn-123-uuid | Pré-config no Fabric |
| **location** | mycontainer | Container name |
| **subpath** | /data/raw | Path dentro container |

### Amazon S3

```http
{
  "path": "Files/S3Data",
  "name": "s3_bucket_link",
  "target": {
    "amazonS3": {
      "connectionId": "{s3-connection-id}",
      "location": "my-bucket",
      "subpath": "/datasets/sales"
    }
  }
}
```

### Azure Blob Storage

```http
{
  "path": "Files/Blob",
  "name": "blob_archive",
  "target": {
    "azureBlobStorage": {
      "connectionId": "{blob-connection-id}",
      "location": "mycontainer",
      "subpath": "/archive"
    }
  }
}
```

### Dataverse (Microsoft Dynamics)

```http
{
  "path": "Tables",
  "name": "dataverse_customers",
  "target": {
    "dataverse": {
      "connectionId": "{dv-connection-id}",
      "environmentDomain": "org123.dynamics.com",
      "tableName": "accounts",
      "deltaLakeFolder": "/dataverse_sync"
    }
  }
}
```

### Google Cloud Storage

```http
{
  "path": "Files/GCS",
  "name": "gcs_bucket",
  "target": {
    "googleCloudStorage": {
      "connectionId": "{gcs-connection-id}",
      "location": "my-bucket",
      "subpath": "/data"
    }
  }
}
```

### S3-Compatible (Minio, etc)

```http
{
  "path": "Files/S3Compat",
  "name": "minio_shortcut",
  "target": {
    "s3Compatible": {
      "connectionId": "{s3compat-connection-id}",
      "bucket": "my-bucket",
      "location": "s3compat.example.com",
      "subpath": "/warehouse"
    }
  }
}
```

---

## Conflict Policies (Resolução de Nomes)

Quando shortcut já existe:

| Policy | Ação | Uso |
|--------|------|-----|
| **Abort** | Falha (padrão) | Evitar overwrites acidentais |
| **GenerateUniqueName** | `dim_customer_1`, `dim_customer_2` | Coexistência de versões |
| **CreateOrOverwrite** | Sobrescreve | Atualizar dados |
| **OverwriteOnly** | Erro se não existe | Append-only (seguro) |

```http
POST /workspaces/{workspace-id}/items/{lakehouse-id}/shortcuts?shortcutConflictPolicy=GenerateUniqueName
```

---

## Mirroring (Sincronização Contínua)

Mirroring é shortcut com **sincronização automática** (unidirecional):

### Configurar Mirror (Databricks → Fabric)

```http
POST /workspaces/{workspace-id}/items/{lakehouse-id}/mirroring
{
  "name": "databricks_orders_mirror",
  "path": "Tables",
  "sourceType": "databricks",
  "sourceProperties": {
    "workspaceUrl": "https://<workspace-instance>.cloud.databricks.com",
    "tablePath": "catalog.schema.orders",
    "authType": "PersonalAccessToken"
  },
  "syncPolicy": {
    "syncType": "ContinuousSync",
    "interval": 3600  // 1 hour
  }
}
```

### Monitorar Mirror

```http
GET /workspaces/{workspace-id}/items/{lakehouse-id}/mirroring/{mirror-id}/status

Response:
{
  "lastSyncTime": "2026-04-09T15:30:00Z",
  "nextSyncTime": "2026-04-09T16:30:00Z",
  "status": "Healthy",
  "rowsAddedSinceSync": 1250
}
```

| Propriedade | Valor | Impacto |
|------------|-------|--------|
| **syncType** | ContinuousSync | Atualiza automaticamente |
| **syncType** | ScheduledSync | Manualmente ou cron |
| **interval** | 3600 (segundos) | 1 hora = bom default |

---

## Fabric ↔ Databricks: Integração via Unity Catalog

### Padrão: Compartilhar via ABFSS Path

Databricks e Fabric acessam **mesmo ADLS Gen2 backend**:

```
ADLS Gen2: mycompany-datalake/
├── databricks/
│   ├── raw_data/ (Databricks escreve)
│   └── processed/ (Databricks output)
└── fabric/
    ├── Gold/ (Fabric Gold tables)
    └── Archive/ (Fabric output)
```

**Databricks (PySpark):**
```python
# Databricks escreve Unity Catalog
# Backend: ADLS Gen2
df.write.format("delta") \
  .mode("overwrite") \
  .save("abfss://databricks@adls.dfs.core.windows.net/raw_data/customers")
```

**Fabric (Spark):**
```python
# Fabric lê via shortcut para Unity Catalog location
df = spark.read.table("uc_catalog.schemas.raw_customers")
```

### Shortcut para Unity Catalog (External Location)

```http
POST /workspaces/{workspace-id}/items/{lakehouse-id}/shortcuts
{
  "path": "Tables",
  "name": "uc_customers",
  "target": {
    "adlsGen2": {
      "connectionId": "{shared-adls-connection}",
      "location": "unity-catalog-external-location",
      "subpath": "/schemas/raw_customers"
    }
  }
}
```

---

## Deployment Pipelines (dev → test → prod)

Pipelines permitem promover conteúdo entre workspaces com REST API:

### Criar Deployment Pipeline

```http
POST /workspaces/{workspace-id}/deploymentPipelines
{
  "displayName": "SalesAnalytics Pipeline",
  "stages": [
    {"displayName": "Development"},
    {"displayName": "Staging"},
    {"displayName": "Production"}
  ]
}
```

### Atribuir Workspace a Stage

```http
POST /deploymentPipelines/{pipeline-id}/stages/{stage-id}/assignWorkspace
{
  "workspaceId": "{workspace-id}"
}
```

**Estrutura:**
```
Deployment Pipeline
├── Development (dev-workspace)
│   ├── Lakehouse (Gold tables)
│   ├── Semantic Model (Power BI)
│   └── Reports
├── Staging (test-workspace)
└── Production (prod-workspace)
```

### Deploy Stage Content

```http
POST /deploymentPipelines/{pipeline-id}/deploy
{
  "sourceStageId": "{dev-stage-id}",
  "targetStageId": "{test-stage-id}",
  "items": [
    {
      "sourceItemId": "{lakehouse-id}",
      "itemType": "Lakehouse"
    },
    {
      "sourceItemId": "{semantic-model-id}",
      "itemType": "SemanticModel"
    }
  ],
  "options": {
    "allowCrossRegionDeployment": true
  }
}
```

### Monitorar Deployment (LRO)

```http
GET /workspaces/{workspace-id}/deploymentPipelines/{pipeline-id}/operations/{operation-id}

Response:
{
  "status": "Succeeded",
  "itemsDeployed": 3,
  "startedAt": "2026-04-09T15:00:00Z",
  "completedAt": "2026-04-09T15:05:30Z"
}
```

---

## Git Integration (GitHub & Azure DevOps)

### GitHub Connect (Fabric → GitHub)

```http
POST /workspaces/{workspace-id}/git/connect
{
  "gitProviderDetails": {
    "gitProviderType": "GitHub",
    "ownerName": "mycompany",
    "repositoryName": "fabric-workspace",
    "branchName": "main",
    "directoryName": "/"
  },
  "myGitCredentials": {
    "source": "ConfiguredConnection",
    "connectionId": "{github-connection-id}"
  }
}
```

### Azure DevOps Connect (Fabric → ADO)

```http
POST /workspaces/{workspace-id}/git/connect
{
  "gitProviderDetails": {
    "gitProviderType": "AzureDevOps",
    "organizationName": "myorg",
    "projectName": "DataPlatform",
    "repositoryName": "fabric-repo",
    "branchName": "develop",
    "directoryName": "/src"
  },
  "myGitCredentials": {
    "source": "ConfiguredConnection",
    "connectionId": "{ado-connection-id}"
  }
}
```

### Commit para Git

```http
POST /workspaces/{workspace-id}/git/commitToGit
{
  "mode": "All",
  "comment": "Deploy Gold layer schema changes"
}
```

**Selective Commit:**
```http
POST /workspaces/{workspace-id}/git/commitToGit
{
  "mode": "Selective",
  "comment": "Update customer dimension",
  "items": [
    {
      "itemId": "{lakehouse-id}",
      "itemType": "Lakehouse"
    }
  ]
}
```

### Update from Git (Pull)

```http
POST /workspaces/{workspace-id}/git/updateFromGit
{
  "remoteCommitHash": "{latest-commit-hash}",
  "conflictResolution": {
    "conflictResolutionPolicy": "PreferRemote"
  }
}
```

| Policy | Ação | Caso |
|--------|------|------|
| **PreferRemote** | Git sobrescreve workspace | CI/CD automático |
| **PreferWorkspace** | Workspace sobrescreve Git | Local changes first |

### Git Status

```http
GET /workspaces/{workspace-id}/git/status

Response:
{
  "remoteCommitHash": "abc123def456",
  "workspaceHead": "def789ghi012",
  "isBehind": true
}
```

---

## Resolução de Conflitos Git

### Cenário: Conflito ao Commit

```
Workspace: Schema change (ALTER TABLE dim_product)
Remote: Delete column (ALTER TABLE dim_product DROP COLUMN cost)
```

**Resolução:**
1. `updateFromGit(PreferRemote)` → puxa remote
2. Reaplique schema change localmente
3. `commitToGit()` novamente

**Padrão:**
```python
# 1. Sync com remote
update_from_git(workspace, conflict_resolution_policy="PreferRemote")

# 2. Reaplique suas mudanças
create_lakehouse(..., enable_schemas=True)

# 3. Commit atualizado
commit_to_git(workspace, mode="All", comment="Reapply schema after conflict resolution")
```

---

## Decision Tree: Shortcut vs Copy vs Mirror

```
Preciso de dados externos?
├─ Real-time (< 1 min latência)?
│  └─ Não → Shortcut ✓ (zero-copy)
│  └─ Sim → Mirror (continuous sync)
├─ Dados volumosos (> 100GB)?
│  └─ Copy Activity ✓ (batch efficient)
├─ Múltiplas transformações?
│  └─ Copy → Dataflow Gen2 (separar concerns)
└─ Dados seguros/PII?
   └─ Não use shortcut → Copy com masking
```

---

## Checklist Cross-Platform Integration

- [ ] Conexões ADLS/S3/GCS criadas no Fabric
- [ ] Shortcuts testados (Abort policy initially)
- [ ] Mirror sync validado (0 failures > 24h)
- [ ] Deployment pipeline: dev → test → prod
- [ ] Git conectado (GitHub ou Azure DevOps)
- [ ] Commit automático via CI/CD (main branch)
- [ ] Conflict resolution policy documentada
- [ ] Lineage rastreado entre workspaces
- [ ] Governança: sensitivity labels em shortcuts
- [ ] Backup: snapshots de Gold antes de promote
