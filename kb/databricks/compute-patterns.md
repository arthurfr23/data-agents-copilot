# Compute — Padrões e Decisão

**Propósito:** Matriz de decisão para escolher entre Serverless SQL, Job Clusters, Interactive Clusters, Databricks Connect e Serverless Compute.

---

## Matriz de Decisão: Qual Compute Usar?

| Critério | **Databricks Connect** ⭐ | **Serverless SQL** | **Job Clusters** | **Interactive Clusters** | **Serverless Compute** |
|----------|-----|----------|-----------|--------|---------|
| **Tipo de código** | PySpark ETL | SQL queries | Multi-task DAG | Exploração ad-hoc | Python/SQL batch |
| **Startup** | Instant (local) | ~5-10s | ~2-5min | ~5-8min | ~25-50s |
| **Custo** | Sem DBU | Por query | DBU compartilhado | DBU + overhead | DBU serverless |
| **State/Sessão** | Dentro do Python | Nenhuma | Nenhuma | Mantém entre chamadas | Nenhuma |
| **Linguagens** | Python/PySpark | SQL | Python/SQL/Scala | Python/Scala/SQL/R | Python/SQL |
| **Quando usar** | ETL rápido, testes | Dashboard, queries | Pipelines 24/7 | Notebooks exploração | Heavy ML/batch |
| **Vantagem** | Mais rápido | Sem cluster manage | Reutilizável | Full language suporte | Escalável |
| **Desvantagem** | Requer Python local | SQL-only | Setup inicial | Caro + overhead | Sem state |

---

## Fluxo de Decisão

```
┌─ Código PySpark + dados < 1GB?
│  └─ SIM → Databricks Connect (RECOMENDADO)
│
├─ SQL puro (dashboard/report)?
│  └─ SIM → Serverless SQL Warehouse
│
├─ Multi-task com dependências?
│  └─ SIM → Job Clusters (em Jobs)
│
├─ Python 3.12 não disponível localmente?
│  ├─ Tenta instalar → Databricks Connect requer >= 16.4
│  └─ Falha? → Não force. Alterne para Job serverless
│
├─ Machine Learning heavy (> 1h execução)?
│  └─ SIM → Serverless Compute (em Jobs)
│
└─ Precisa explorar/iterar com state?
   └─ SIM → Interactive Cluster (lista clusters e pergunta qual usar)
```

---

## 1. Databricks Connect — PySpark Local

**Perfeito para:** ETL rápido, testes, desenvolvimento.

### Setup (Necessário Python 3.12)

```bash
# Instalar Python 3.12 (se necessário)
python3.12 --version

# Instalar databricks-connect >= 16.4
pip install databricks-connect==16.4.0

# Configurar profile
databricks configure --token --profile databricks
```

### Usar em Código

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder.remote(url="<workspace-url>", token="<token>").build()

# Tudo roda em cluster remoto, resultado local
df = spark.read.table("main.analytics.users")
df.count()  # Executa no Databricks, retorna resultado
```

**Gotcha:** Python 3.12 é **mandatório** para databricks-connect >= 16.4. Versões antigas falham silenciosamente.

---

## 2. Serverless SQL Warehouse

**Perfeito para:** Dashboards, queries SQL, BI tools.

**Características:**
- Startup ~5-10 segundos
- Sem cluster management
- Pagamento por query

**Criar warehouse:**
```bash
databricks warehouses create --name "Analytics WH" \
  --cluster_size "2xlarge" \
  --auto_stop_mins 10
```

**Gotcha:** Não é "compute", é **gateway SQL**. Não execute PySpark direto.

---

## 3. Job Clusters — Pipelines Produção

**Perfeito para:** Multi-task DAGs em Jobs, execuções automáticas.

**Definição em DAB (Resources):**
```yaml
resources:
  jobs:
    etl_job:
      tasks:
        - task_key: extract
          job_cluster_key: shared_compute
          notebook_task:
            notebook_path: ../src/extract.py

  job_clusters:
    - job_cluster_key: shared_compute
      new_cluster:
        spark_version: "15.4.x-scala2.12"
        node_type_id: "i3.xlarge"
        num_workers: 2
        spark_conf:
          spark.speculation: "true"
        aws_attributes:
          availability: "SPOT_WITH_FALLBACK"
```

**Vantagens:**
- Reutilizável entre tasks
- Configuração declarativa
- Auto-escalável com `autoscale`

**Gotcha:** Cluster sobe quando job inicia, desce ao final. Cada task nova não reutiliza cluster anterior (unless `job_cluster_key`).

---

## 4. Interactive Clusters — Exploração Ad-Hoc

**Perfeito para:** Notebooks exploração, Scala/R, state entre chamadas.

**NUNCA inicie cluster sem perguntar ao usuário.** Startup é ~5-8 minutos.

```python
# 1. Listar clusters
result = list_compute(resource="clusters")
# Exibir ao usuário: "Qual cluster usar?"

# 2. Executar código, reutilizar context_id
first_result = execute_code(
    code="df = spark.read.table('main.data.users')",
    compute_type="cluster",
    cluster_id="<user-selected-id>"
)

second_result = execute_code(
    code="df.count()",
    context_id=first_result["context_id"],  # Reutilizar state
    cluster_id=first_result["cluster_id"]
)
```

**Auto-termination (Obrigatório):**
```yaml
spark_conf:
  spark.databricks.cluster.profile: "singleNode"

autotermination_minutes: 20  # Desligar após 20min inativo
```

**Gotcha:** Sem `autotermination_minutes`, cluster roda 24/7 e consome DBU continuamente.

---

## 5. Serverless Compute — Heavy ML/Batch

**Perfeito para:** Model training, batch processing, sem cluster management.

**Em Jobs (sem config de cluster):**
```yaml
resources:
  jobs:
    training_job:
      tasks:
        - task_key: train_model
          python_wheel_task:
            package_name: "ml_package"
            entry_point: "train"
            # Sem cluster_key ou new_cluster → serverless
```

**Startup:** ~25-50 segundos. Sem estado entre tasks.

**Gotcha:** Serverless não mantém state. Cada task é isolada; use Volume ou Delta table para passar dados.

---

## Matriz de Custo (Estimativa)

| Tipo | Custo/Hora | Startup | Melhor Para |
|------|-----------|---------|------------|
| Databricks Connect | Gratuito (local) | Instant | Testes, dev |
| Serverless SQL | ~$2-5/query | 5-10s | Queries BI |
| Job Cluster 2 workers | ~$1-2 (DBU) | 2-5min | Pipelines |
| Interactive 2 workers | ~$1-2 (DBU) + overhead | 5-8min | Exploração |
| Serverless Compute | ~$2-4 (DBU serverless) | 25-50s | ML heavy |

---

## Boas Práticas Críticas

### 1. Nunca Inicie Cluster sem Pergunta
```python
# ❌ Errado
manage_cluster(action="start", cluster_id="...")  # Sem confirmação

# ✅ Certo
print("Deseja iniciar cluster X? Startup é ~5 minutos.")
# Aguardar confirmação do usuário
```

### 2. Sempre Configure Auto-Termination em Interactive
```yaml
autotermination_minutes: 15  # Padrão recomendado
```

### 3. Python 3.12 para Databricks Connect
```bash
# Verificar versão
python3.12 --version

# Se < 3.12, atualizar ou usar Job serverless
```

### 4. Prefira Serverless para SQL
```sql
-- Usar Serverless SQL Warehouse, não cluster para SQL puro
SELECT COUNT(*) FROM main.analytics.users;
```

### 5. Job Clusters para Pipelines Produção
```yaml
# Reutilizável, custo fixo, auto-escalável
job_cluster_key: shared_compute
```

---

## Checklist de Implementação

- [ ] Databricks Connect instalado com Python 3.12
- [ ] Serverless SQL Warehouse criado para queries BI
- [ ] Job Clusters definidos em DAB para pipelines
- [ ] Auto-termination = 15-20 min em Interactive Clusters
- [ ] Nenhum cluster inicia sem confirmação do usuário
- [ ] Spark Config validado (speculation, dynamicAllocation, etc.)
