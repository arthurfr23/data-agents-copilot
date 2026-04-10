# AI & ML — Padrões MLflow, Model Serving, Vector Search, AI Functions

**Propósito:** Referência rápida para ML workflows no Databricks: MLflow, pyfunc models, Model Serving, Vector Search e AI Functions.

---

## MLflow — Logging e Rastreamento

### Autolog (Automático)

MLflow pode rastrear automaticamente experimentos sem código manual:

```python
import mlflow
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_breast_cancer

# Ativar autolog
mlflow.autolog()

# Training automático registrado
with mlflow.start_run():
    X, y = load_breast_cancer(return_X_y=True)
    model = RandomForestClassifier()
    model.fit(X, y)
    # Autolog captura: params, metrics, model, training time
```

**Gotcha:** Autolog funciona para libraries populares (sklearn, xgboost, tensorflow). Custom models requerem log manual.

### Manual Logging — PythonModel (Recomendado)

Encapsule lógica customizada em `PythonModel`:

```python
import mlflow
from mlflow.pyfunc import PythonModel, log_model

class MyCustomModel(PythonModel):
    def __init__(self):
        self.preprocessor = load_preprocessor()

    def predict(self, context, model_input):
        # Lógica de predição
        cleaned = self.preprocessor.transform(model_input)
        predictions = self.model.predict(cleaned)
        return predictions

# Log com resources
with mlflow.start_run() as run:
    model = MyCustomModel()
    log_model(
        model,
        artifact_path="model",
        python_model=model,
        registered_model_name="my_model",
        resources=[
            {
                "type": "python_package",
                "package": "numpy==1.24.0"
            }
        ]
    )
```

**Gotcha:** `resources` parameter declara dependências. Sem ele, Model Serving falha por imports.

---

## Model Serving — Deployment e Serving

### Endpoint Creation

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput

w = WorkspaceClient()

endpoint_config = EndpointCoreConfigInput(
    name="my-model-endpoint",
    served_models=[
        {
            "model_name": "my_model",
            "model_version": "1",
            "workload_size": "Small"
        }
    ]
)

endpoint = w.serving_endpoints.create(config=endpoint_config)
```

### Query Endpoint

```python
import requests
import json

endpoint_url = "https://<workspace-url>/api/2.0/endpoints/my-model-endpoint/invocations"

payload = {
    "dataframe_split": {
        "columns": ["feature1", "feature2"],
        "data": [[1.0, 2.0], [3.0, 4.0]]
    }
}

response = requests.post(
    endpoint_url,
    headers={"Authorization": f"Bearer {token}"},
    json=payload
)

predictions = response.json()["predictions"]
```

**Deployment Time:** ~15 minutos para cold start. Planeje em CI/CD.

### Foundation Models (Endpoints)

Para modelos de fundação (Claude, GPT, Llama), nomes de endpoint **devem ser exatos**:

```python
# ✅ Nome exato requerido
endpoint_name = "databricks-claude-3-5-sonnet"  # Exato
endpoint_name = "databricks-meta-llama-3-70b-instruct"

# ❌ Variações falham
endpoint_name = "claude"  # Não encontrado
endpoint_name = "Databricks-Claude"  # Case-sensitive
```

**Gotcha:** Foundation Model endpoint names são case-sensitive e exatos. Typos resultam em 404.

### ResponsesAgent Helper Methods (Mandatório)

Para agentic workflows com foundation models:

```python
from databricks.genai.agent_api import ResponsesAgent

# ResponsesAgent métodos requeridos
agent = ResponsesAgent(
    model="databricks-claude-3-5-sonnet",
    temperature=0.7,
    max_tokens=1024
)

response = agent.respond(
    prompt="Analise este dataset...",
    context_data=df  # Context automático
)
```

**Gotcha:** Sem ResponsesAgent helper, deployment em Model Serving falha. Não use raw requests para foundational models em produção.

---

## Vector Search — Indexação e Sync

Vector Search integra com Unity Catalog tables. Dois modos de índice:

### 1. Delta Sync Index (Recomendado)

Sincroniza automaticamente com tabela Delta:

```python
from databricks.vector_search.client import VectorSearchClient

client = VectorSearchClient()

index = client.create_delta_sync_index(
    endpoint_name="my-endpoint",
    index_name="doc_index",
    primary_key="doc_id",
    delta_sync_index_config={
        "data_objects": [
            {
                "table_name": "main.docs.documents",
                "text_search_config": {
                    "field_name": "content",
                    "chunk_template": "{{content}}"  # Template de texto
                },
                "embedding_source_columns": ["content"],
                "embedding_model": "databricks-bge-large-en"
            }
        ]
    }
)
```

**Vantagem:** Sincronização automática. Sem lag de indexação.

### 2. Direct Index (Manual)

Índice estático — atualizar manualmente:

```python
index = client.create_direct_access_index(
    endpoint_name="my-endpoint",
    index_name="manual_index",
    primary_key="id",
    embedding_dimension=768
)

# Inserir vetores manualmente
index.upsert(
    rows_to_add=[
        {
            "id": "1",
            "text": "Sample document",
            "embedding": [0.1, 0.2, ..., 0.768]  # Embedding pré-calculado
        }
    ]
)
```

**Gotcha:** Direct index requer embedding pré-calculado. Lento para grandes datasets.

### Query Vector Search

```python
results = index.similarity_search(
    query_text="Machine learning",
    columns=["id", "content", "metadata"],
    num_results=5
)
```

---

## AI Functions — SQL Direto

AI Functions executam LLMs diretamente em SQL:

### ai_query (Consultas Customizadas)

```sql
SELECT ai_query(
    'main.genai.ai_fn',
    'Sumarize este texto: ' || content,
    model => 'databricks-claude-3-5-sonnet'
) AS summary
FROM main.docs.articles;
```

### ai_forecast (Previsões)

```sql
SELECT ai_forecast(
    'main.genai.forecast_fn',
    STRUCT(date, sales, trend),
    model => 'databricks-claude-3-5-sonnet'
) AS predicted_sales
FROM main.analytics.sales_history
WHERE date >= current_date() - 30;
```

### ai_generate (Geração)

```sql
SELECT ai_generate(
    'main.genai.gen_fn',
    STRUCT(product_name, target_audience),
    model => 'databricks-claude-3-5-sonnet',
    temperature => 0.8
) AS marketing_copy
FROM main.products.catalog;
```

**Gotcha:** AI Functions requerem função Python wrapper. Não são queries "magic". Requerem setup prévio.

---

## Matriz de Decisão: ML Approach

| Cenário | Tipo | Implementação | Vantagem | Desvantagem |
|---------|------|---------------|----------|------------|
| **Classificação tabular** | Classical ML | sklearn + AutoML | Rápido, interpretável | Sem deep learning |
| **Custom lógica + dados** | PythonModel | MLflow pyfunc | Flexível, rastreável | Mais setup |
| **GenAI agent** | Foundation Model | ResponsesAgent | SOTA, multi-modal | Latência 1-5s, custo |
| **Embeddings + search** | Vector Search | Delta-sync index | Real-time, escalável | Setup embedding |
| **SQL + ML** | AI Functions | ai_query, ai_forecast | Integrado, sem ETL | Overhead SQL |

---

## Boas Práticas Críticas

### 1. Sempre Declarar Resources em MLflow
```python
# ✅ Com resources
log_model(
    model,
    python_model=model,
    resources=[{"type": "python_package", "package": "numpy==1.24.0"}]
)

# ❌ Sem resources — Model Serving falha
log_model(model, python_model=model)
```

### 2. Foundation Model Names Exatos
```python
# ✅ Exato
model_name = "databricks-claude-3-5-sonnet"

# ❌ Typo/case-sensitive
model_name = "claude-3-5-sonnet"  # Não encontrado
```

### 3. Vector Search Delta-Sync para Datasets Dinâmicos
```python
# ✅ Sincronização automática
create_delta_sync_index(...)

# ❌ Manual — defasado em minutos
create_direct_access_index(...)
```

### 4. Timeout para Model Serving (~15 min)
```python
# Deployment leva ~15 minutos para cold start
# Não cancele esperando mais rápido
time.sleep(900)  # Aguardar 15 min
endpoint = w.serving_endpoints.get("my-endpoint")
```

### 5. AI Functions Requerem Python Wrapper
```sql
-- ❌ Não funciona direto
SELECT ai_query('Sumarize X');

-- ✅ Requer função Python
CREATE FUNCTION summarize(text STRING)
RETURNS STRING
LANGUAGE PYTHON
AS $$
from databricks_genai import ...
return summarize_fn(text)
$$
```

---

## Matriz: MLflow vs Vector Search vs AI Functions

| Aspecto | MLflow | Vector Search | AI Functions |
|--------|--------|---------------|--------------|
| **Caso** | Classificação, regression | Semantic search | SQL queries GenAI |
| **Latência** | < 100ms | < 500ms | 1-5s |
| **Custo** | DBU | Endpoint | Tokens LLM |
| **Setup** | Simple | Médio (embeddings) | Complexo (wrapper) |
| **Escala** | 1M+ predições | 1M+ docs | 10K+ queries/dia |

---

## Checklist Implementação

- [ ] MLflow autolog ativado para sklearn/xgboost
- [ ] Custom models com PythonModel + resources declarados
- [ ] Model Serving endpoint criado e testado
- [ ] Foundation Model endpoint name exato (case-sensitive)
- [ ] ResponsesAgent para agentic workflows
- [ ] Vector Search delta-sync para datasets dinâmicos
- [ ] AI Functions com Python wrapper testado
- [ ] Timeout de 15 min considerado em CI/CD
- [ ] Embedding model selecionado (bge-large-en default)
- [ ] Logging de experimentos vinculado a runs (MLflow)
