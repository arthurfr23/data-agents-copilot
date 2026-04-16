<p align="center">
  <img src="img/readme/banner.svg" alt="Data Agents" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-8.0.0-brightgreen" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.12+-blue" alt="Python">
  <img src="https://img.shields.io/badge/Databricks-MCP-FF3621" alt="Databricks">
  <img src="https://img.shields.io/badge/Microsoft%20Fabric-MCP-0078D4" alt="Fabric">
  <img src="https://img.shields.io/badge/Anthropic-Claude%20SDK-D97757" alt="Claude SDK">
  <img src="https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF" alt="CI/CD">
</p>

**Data Agents** é um sistema multi-agente construído sobre o **Claude Agent SDK** da Anthropic com integração nativa via **Model Context Protocol (MCP)** ao **Databricks** e **Microsoft Fabric**. Em vez de um único assistente genérico, o sistema orquestra **10 agentes especialistas** que operam diretamente nas suas plataformas de dados, cada um com seu domínio de conhecimento, ferramentas e regras corporativas declarativas.

---

## Autor

> **Thomaz Antonio Rossito Neto**
> Specialist Data & AI Solutions Architect | Center of Excellence CoE @CI&T

**LinkedIn:** [thomaz-antonio-rossito-neto](https://www.linkedin.com/in/thomaz-antonio-rossito-neto/) &nbsp;·&nbsp; **GitHub:** [ThomazRossito](https://github.com/ThomazRossito/)

### Certificações Databricks

<img src="img/readme/badges/db_spark.png" alt="Databricks Certified Spark Developer" width="100"/> <img src="img/readme/badges/db_genai.png" alt="Databricks Certified Generative AI Engineer Associate" width="100"/> <img src="img/readme/badges/db_analyst.png" alt="Databricks Certified Data Analyst Associate" width="100"/> <img src="img/readme/badges/db_de_associate.png" alt="Databricks Certified Data Engineer Associate" width="100"/> <img src="img/readme/badges/db_de_professional.png" alt="Databricks Certified Data Engineer Professional" width="100"/>

### Certificações Microsoft

<a href="https://www.credly.com/badges/052e5133-0c67-4ab7-bb3a-c99efa7b4406/public_url"><img src="img/readme/badges/ms_dp900.png" alt="DP-900" width="100"/></a> <a href="https://learn.microsoft.com/pt-br/users/thomazantoniorossitoneto/credentials/certification/fabric-data-engineer-associate"><img src="img/readme/badges/ms_dp700.png" alt="DP-700" width="100"/></a>

---

## Como Funciona

<p align="center">
  <img src="img/readme/architecture_v8.svg" alt="Arquitetura Data Agents v8" width="100%">
</p>

Você envia uma mensagem — seja pelo terminal, pela interface web ou com um comando slash. O **Supervisor** lê a solicitação, consulta as bases de conhecimento do projeto, planeja a solução e delega para os agentes especialistas certos. Cada agente usa as ferramentas MCP para operar diretamente no Databricks ou no Microsoft Fabric e devolve o resultado para o Supervisor consolidar.

**O Supervisor nunca escreve código ou acessa dados diretamente** — ele coordena. Os especialistas executam.

---

## Início Rápido

```bash
# 1. Clone e entre no diretório
git clone git@github.com:ThomazRossito/data-agents.git && cd data-agents

# 2. Crie o ambiente
conda create -n data-agents python=3.12 && conda activate data-agents

# 3. Instale dependências
pip install -e ".[dev,ui,monitoring]"

# 4. Configure credenciais
cp .env.example .env   # edite com suas chaves

# 5a. Web UI Chainlit (recomendada)
./start_chainlit.sh    # http://localhost:8503

# 5b. Web UI Streamlit
./start.sh             # http://localhost:8502 (Chat) + http://localhost:8501 (Monitoring)

# 5c. Terminal
python main.py
```

### Credenciais no `.env`

| Variável | Obrigatória | Plataforma |
|----------|-------------|------------|
| `ANTHROPIC_API_KEY` | Sim | Claude API |
| `DATABRICKS_HOST`, `DATABRICKS_TOKEN` | Não | Databricks |
| `AZURE_TENANT_ID`, `FABRIC_WORKSPACE_ID` | Não | Microsoft Fabric |
| `TAVILY_API_KEY` | Não | Busca web |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | Não | GitHub MCP |
| `FIRECRAWL_API_KEY` | Não | Web scraping |
| `POSTGRES_URL` | Não | PostgreSQL MCP |

> O sistema ativa automaticamente apenas as plataformas com credenciais configuradas. `context7` e `memory_mcp` são ativados sempre, sem credenciais.

---

## Agentes Especialistas

| Agente | Comando | Tier | O que faz |
|--------|---------|------|-----------|
| **Supervisor** | `/plan` | — | Coordena, planeja e valida tudo contra a Constituição |
| **Business Analyst** | `/brief` | T3 | Converte reuniões e briefings em backlog P0/P1/P2 |
| **SQL Expert** | `/sql` | T1 | SQL (Spark SQL, T-SQL, KQL), schemas, Unity Catalog |
| **Spark Expert** | `/spark` | T1 | PySpark, Delta Lake, pipelines Medallion |
| **Pipeline Architect** | `/pipeline` | T1 | ETL/ELT, orquestração, cross-platform Databricks ↔ Fabric |
| **dbt Expert** | `/dbt` | T2 | dbt Core: models, testes, snapshots, seeds, docs |
| **Data Quality Steward** | `/quality` | T2 | Validação de dados, profiling, alertas, SLAs |
| **Governance Auditor** | `/governance` | T2 | Auditoria de acessos, linhagem, PII, LGPD/GDPR |
| **Semantic Modeler** | `/semantic` | T2 | DAX, Direct Lake, Genie Spaces, AI/BI Dashboards |
| **Geral** | `/geral` | T3 | Respostas conceituais diretas — zero MCP, ~95% mais barato |

### Party Mode — Múltiplos Especialistas em Paralelo

O comando `/party` convoca 2 a 6 agentes simultaneamente para a mesma pergunta. Cada um responde de forma independente, com sua perspectiva de domínio.

```bash
/party qual a diferença entre Delta Lake e Iceberg?
# → sql-expert + spark-expert + pipeline-architect respondem em paralelo

/party --quality como garantir qualidade em dados incrementais?
# → data-quality-steward + governance-auditor + semantic-modeler

/party --full explique o Unity Catalog
# → todos os 6 agentes especialistas
```

---

## Comandos Disponíveis

| Comando | Descrição |
|---------|-----------|
| `/sql <query>` | SQL direto para o sql-expert |
| `/spark <tarefa>` | PySpark/DLT direto para o spark-expert |
| `/pipeline <tarefa>` | Pipeline ETL direto para o pipeline-architect |
| `/dbt <tarefa>` | dbt Core direto para o dbt-expert |
| `/quality <tarefa>` | Qualidade de dados direta |
| `/governance <tarefa>` | Auditoria e governança direta |
| `/semantic <tarefa>` | Modelagem semântica direta |
| `/brief <texto>` | Converte transcript/briefing em backlog estruturado |
| `/plan <objetivo>` | Planejamento completo com thinking habilitado (8k tokens) |
| `/review <artefato>` | Review de código ou pipeline |
| `/party <query>` | Multi-agente paralelo (flags: `--quality`, `--arch`, `--full`) |
| `/geral <pergunta>` | Resposta direta sem Supervisor — mais rápido e barato |
| `/health` | Status das plataformas configuradas |
| `/status` | Estado da sessão atual |
| `/memory <query>` | Consulta à memória persistente |

---

## Protocolo DOMA

O Supervisor segue o **Método DOMA** (Data Orchestration Method for Agents) — um protocolo de 7 passos que garante que qualquer tarefa complexa seja bem planejada antes de ser executada:

```
Passo 0    KB-First: consulta as bases de conhecimento antes de qualquer plano
Passo 0.5  Clarity Checkpoint: valida se a solicitação está clara o suficiente
Passo 0.9  Spec-First: seleciona o template adequado para a tarefa
Passo 1    Planejamento: cria um documento de requisitos (PRD) em output/prd/
Passo 2    Aprovação: aguarda confirmação antes de executar
Passo 3    Delegação: aciona os agentes especialistas na ordem certa
Passo 4    Validação: verifica se o resultado segue as regras da Constituição
```

Para perguntas simples e comandos diretos (`/sql`, `/spark`, etc.), o Supervisor usa **DOMA Express** — pula o planejamento e delega diretamente.

### Workflows Colaborativos

Para projetos end-to-end, o Supervisor encadeia agentes automaticamente:

| Workflow | Quando usar | Agentes envolvidos |
|----------|-------------|-------------------|
| **WF-01** Pipeline End-to-End | "Crie um pipeline Bronze→Gold completo" | Spark → Quality → Semantic → Governance |
| **WF-02** Star Schema | "Crie a camada Gold em Star Schema" | SQL → Spark → Quality → Semantic |
| **WF-03** Migração Cross-Platform | "Migre do Databricks para o Fabric" | Architect → SQL → Spark → Quality + Governance |
| **WF-04** Auditoria de Governança | "Gere um relatório de compliance" | Governance → Quality → Relatório |

---

## Plataformas e MCPs

O sistema conecta diretamente às plataformas via Model Context Protocol (MCP):

| MCP | Plataforma | Principais capacidades |
|-----|------------|----------------------|
| `databricks` | Databricks | SQL, listagem de tabelas, clusters, jobs, model serving |
| `databricks_genie` | Databricks Genie | Conversational BI, espaços Genie |
| `fabric` | Microsoft Fabric | REST API, workspaces, itens, pipelines |
| `fabric_sql` | Fabric SQL Analytics | Queries diretas ao Lakehouse via TDS |
| `fabric_rti` | Fabric RTI | KQL, Kusto, Real-Time Intelligence |
| `fabric_community` | Fabric | Linhagem de dados, dependências entre itens |
| `context7` | Docs de bibliotecas | Documentação atualizada de qualquer lib |
| `tavily` | Web | Busca web para LLMs |
| `github` | GitHub | Repos, issues, PRs |
| `firecrawl` | Web | Scraping estruturado de páginas |
| `postgres` | PostgreSQL | Queries readonly em bancos externos |
| `memory_mcp` | Local | Knowledge graph persistente de entidades |

---

## Camada de Proteção

Hooks automáticos protegem todas as operações:

| Hook | Proteção |
|------|----------|
| `security_hook` | Bloqueia 22 padrões destrutivos (DROP, rm -rf, git reset --hard, etc.) |
| `check_sql_cost` | Bloqueia `SELECT *` sem `WHERE` ou `LIMIT` |
| `audit_hook` | Registra todas as chamadas de ferramentas em JSONL |
| `cost_guard_hook` | Classifica operações por custo (HIGH/MEDIUM/LOW) e alerta |
| `output_compressor` | Trunca outputs verbosos para não desperdiçar contexto |
| `context_budget_hook` | Alerta a 80% e 95% do limite de contexto por agente |
| `workflow_tracker` | Rastreia delegações, Clarity Checkpoint e cascade PRD→SPEC |
| `memory_hook` | Captura contexto da sessão para memória persistente |

---

## Sistema de Memória

Memória persistente em dois níveis:

**Episódica (`memory/`):** Captura fatos da sessão automaticamente. Aplica decay temporal — memórias antigas perdem relevância gradualmente. Retrieval semântico antes de cada consulta ao Supervisor.

**Knowledge Graph (`memory_mcp/`):** Grafo de entidades nomeadas (tabelas, pipelines, decisões, times) e suas relações. Gerenciado pelos agentes. Não decai.

```bash
MEMORY_ENABLED=true
MEMORY_RETRIEVAL_ENABLED=true
MEMORY_CAPTURE_ENABLED=true
```

---

## Interfaces

### Web UI Chainlit (recomendada — porta 8503)
Interface com steps expandíveis em tempo real mostrando cada delegação e tool call. Dois modos: **Data Agents** (sistema completo) e **Dev Assistant** (Claude direto com ferramentas de código).

```bash
./start_chainlit.sh
```

### Web UI Streamlit (porta 8502)
Chat com histórico persistente, suporte a todos os slash commands e visualização de artefatos gerados (PRDs, SPECs, Backlogs).

```bash
./start.sh
```

### Dashboard de Monitoramento (porta 8501)
9 páginas: Overview, Agentes, Workflows, Execuções, MCP Servers, Logs, Configurações, Custo e Tokens.

```bash
./start.sh --monitor-only
```

---

## Qualidade e CI/CD

```bash
make lint             # ruff check + format
make type-check       # mypy
make test             # pytest com cobertura mínima 80%
make health-databricks
make health-fabric
```

**CI** (push/PR): lint + format + mypy + pytest (cobertura 80%) + bandit security scan
**CD** (tags): deploy via Databricks Asset Bundles

---

## Configurações Avançadas

| Variável | Default | Descrição |
|----------|---------|-----------|
| `MAX_BUDGET_USD` | 5.0 | Limite de custo por sessão (USD) |
| `MAX_TURNS` | 50 | Limite de turnos por sessão |
| `TIER_MODEL_MAP` | `{}` | Override de modelo por tier |
| `INJECT_KB_INDEX` | true | Injeção automática de KBs nos agentes |
| `IDLE_TIMEOUT_MINUTES` | 30 | Reset automático por inatividade |
| `MEMORY_ENABLED` | true | Sistema de memória persistente |
| `SKILL_REFRESH_INTERVAL_DAYS` | 3 | Intervalo de refresh das Skills |

---

## Manual Técnico Completo

[Manual_Relatorio_Tecnico_Projeto_Data_Agents.md](Manual_Relatorio_Tecnico_Projeto_Data_Agents.md)

---

## Licença

[MIT License](LICENSE)
