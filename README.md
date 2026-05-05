# data-agents-copilot

**Versão enxuta e pessoal de [ThomazRossito/data-agents](https://github.com/ThomazRossito/data-agents), adaptada para rodar via GitHub Copilot Chat API.**

Sistema multi-agente para engenharia de dados (SQL, PySpark, pipelines, governança) que roteia tarefas para agentes IA especializados. Executável via CLI, Chainlit web ou diretamente no VS Code Chat.

> ℹ️ **Antes de tudo:** este é um fork pessoal e propositalmente reduzido do projeto original **[data-agents](https://github.com/ThomazRossito/data-agents)** de [Thomaz Rossito](https://github.com/ThomazRossito). * Este fork é uma adaptação ao meu fluxo de trabalho e aprendizado pessoal.

---

## 🎯 O Que É

Roteador automático que despacha tarefas de dados para agentes IA especializados, com governança de nomenclatura, workflows colaborativos, KB local, memória episódica e protocolo QA peer-to-peer — tudo plugado em GitHub Copilot Chat ao invés do Claude SDK direto.

---

## 🔁 Relação com o Projeto Original

O upstream **[ThomazRossito/data-agents](https://github.com/ThomazRossito/data-agents)** é a fonte e referência canônica. Este fork:

- **Mantém:** Supervisor + agentes especialistas, Party Mode, hooks de segurança/auditoria/custo, integração MCP com Databricks e Fabric, Chainlit como UI principal, sistema de memória, evals.
- **Substitui (parcial):** Anthropic Claude SDK direto → GitHub Copilot Chat API como LLM principal. Anthropic continua como dependência secundária (`qa_reviewer` usa Haiku 4.5; `supervisor` usa Sonnet 4.6 via failover).
- **Adiciona:** Naming Guard com auto-trigger em DDL, workflows WF-06 e WF-07 (no contexto local), QA Orchestrator com score 0–1, failover automático de modelo (Opus → Sonnet → Haiku) com detecção de 529/overloaded.
- **Não tem:** Catalog Intelligence, Migration Expert, Semantic Modeler, Business Analyst, Business Monitor, Genie Health Check, dashboard de monitoramento de 9 páginas, ~13 MCPs adicionais (Genie, Fabric SQL, RTI, Tavily, Firecrawl, Postgres, GitHub, Migration Source, etc.).

### Mapa de equivalências

| Domínio | data-agents (upstream) | data-agents-copilot (fork) |
|---|---|---|
| **LLM** | Anthropic Claude SDK direto | GitHub Copilot Chat API (principal) + Anthropic API (qa_reviewer Haiku, supervisor Sonnet, failover) |
| **Agentes especialistas** | 13 agentes (inclui Catalog Intelligence, Migration Expert, Semantic Modeler, Business Analyst, Business Monitor) | 15 nomes — porém vários compactados; **escopo funcional menor** |
| **MCP servers** | 15+ (Databricks, Genie, Fabric REST, Fabric SQL, RTI, OneLake, Tavily, GitHub, Firecrawl, Postgres, Migration Source, Context7, Memory, Semantic, Community) | 2 servidores standalone (Databricks, Fabric) + tools nativas inline em `agents/tools/` |
| **Workflows** | WF-01 a WF-06 | WF-01 a WF-07 (escopo local; WF-06 e WF-07 são adições experimentais) |
| **Knowledge Base** | KBs internos + **KBs de 10 verticais de indústria** (Financial, Retail, Manufacturing, Healthcare, Energy, Telecom, Agribusiness, Insurance, Logistics, Education) com KPIs e regulação local | `kb/` com 19 domínios técnicos **+ KBs de 10 verticais de indústria** (paridade com upstream) |
| **Memória** | Episódica + Knowledge Graph (memory_mcp) | Episódica com decay temporal + Knowledge Graph local |
| **QA / Review** | Auto-revisão de DDL (10 verificações), Genie Health Check (20 verificações) | QA Orchestrator com score 0–1, threshold 0.7 (mais simples) |
| **Confiabilidade** | Failover Opus → Sonnet → Haiku automático | Failover Opus → Sonnet → Haiku automático (`agents/base.py`, detecção 529/overloaded) |
| **Dashboard** | Monitoring próprio (porta 8501, 9 páginas) + Chainlit (8503) | Apenas Chainlit |
| **Comandos extras** | `/catalog`, `/genie`, `/dashboard`, `/migrate`, `/brief`, `/ship`, `/monitor`, `/export`, `/eval`, `/sessions`, `/resume`, `/mcp` | Subset menor — sem `/catalog`, `/migrate`, `/genie`, `/dashboard`, `/brief`, `/ship` |
| **Evals** | Framework v1 com queries canônicas | 13 queries em 9 domínios |
| **Bootstrap** | `make bootstrap` (wizard interativo) + `make demo` (smoke E2E) | `cp .env.example .env` manual |

---

## 📦 Estrutura

```
data-agents-copilot/
├── agents/
│   ├── registry/           # 15 agentes (system prompts em markdown)
│   │   ├── supervisor.md
│   │   ├── spark_expert.md
│   │   ├── sql_expert.md
│   │   ├── pipeline_architect.md
│   │   ├── data_quality.md
│   │   ├── naming_guard.md
│   │   ├── governance_auditor.md
│   │   ├── dbt_expert.md
│   │   ├── python_expert.md
│   │   ├── fabric_expert.md
│   │   ├── databricks_ai.md
│   │   ├── devops_engineer.md
│   │   ├── lakehouse_engineer.md
│   │   ├── geral.md
│   │   └── qa_reviewer.md
│   ├── tools/              # MCP tools nativas (Databricks + Fabric)
│   ├── loader.py           # Parser do registry + AGENT_COMMANDS
│   ├── base.py             # Classe base BaseAgent (loop OpenAI)
│   ├── health.py           # /health check
│   ├── party.py            # Party Mode (execução paralela)
│   └── supervisor.py       # Roteador principal
├── orchestrator/
│   ├── models.py           # TaskSpec, ScoreReport, ReviewResult
│   └── qa_orchestrator.py  # QA peer orchestrator (auto-ativo)
├── workflow/
│   ├── dag.py              # WF-01 a WF-07 + detect_workflow()
│   └── executor.py         # execute_workflow() com handoff de contexto
├── memory/
│   ├── store.py            # MemoryStore CRUD + thread-safe
│   ├── retrieval.py        # retrieve_relevant_memories()
│   ├── extractor.py        # extract_and_save() via regex
│   ├── decay.py            # compute_decayed_confidence()
│   ├── kg.py               # KnowledgeGraph (entities + relations)
│   └── types.py            # MemoryType, Memory dataclass
├── hooks/
│   ├── audit_hook.py       # Registro JSONL de execuções
│   ├── cost_guard_hook.py  # Budget tracking + reset()
│   ├── security_hook.py    # check_input() + check_output()
│   └── output_compressor.py
├── integrations/
│   ├── fabricgov.py        # fabricgov CLI wrapper
│   └── github_context.py   # fabric-ci-cd context fetch
├── mcp_servers/
│   ├── databricks_server.py  # MCP server standalone (Databricks)
│   └── fabric_server.py      # MCP server standalone (Fabric)
├── evals/
│   ├── canonical_queries.yaml  # 13 queries, 9 domínios
│   └── runner.py               # CLI --domain, --id, --limit, --dry-run
├── kb/                     # 19 domínios técnicos + 10 verticais de indústria
│   ├── constitution.md
│   ├── industry/           # 10 verticais (financial-services, retail, healthcare, ...)
│   ├── sql-patterns/
│   ├── spark-patterns/
│   ├── spark-internals/
│   ├── pipeline-design/
│   ├── data-quality/
│   ├── governance/
│   ├── databricks-platform/
│   ├── databricks-ai/
│   ├── fabric/
│   ├── lakehouse-design/
│   ├── lakehouse-ops/
│   ├── genai/
│   ├── prompt-engineering/
│   ├── data-modeling/
│   ├── ci-cd/
│   ├── orchestration/
│   ├── testing/
│   └── shared/
├── config/
│   └── settings.py         # Pydantic settings (GITHUB_TOKEN opcional)
├── ui/
│   └── chainlit_app.py     # Interface web (lazy init em on_chat_start)
├── resources/
│   ├── naming convention.md   # Convenções editáveis
│   └── jobs.yml               # Config de jobs Databricks
├── tests/                  # 233 testes, cobertura 83%
├── output/
│   ├── prd/                # PRDs gerados (sha1 filename)
│   └── workflows/          # Outputs de workflows
└── main.py                 # CLI entry point
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/arthurfr23/data-agents-copilot.git
cd data-agents-copilot
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # preencher GITHUB_TOKEN
```

### Execução

```bash
# Menu interativo
data-agent

# Acesso direto ao agente
data-agent spark "otimize pipeline Bronze→Silver incremental"
data-agent sql "modele star schema para vendas com SCD2"
data-agent naming "CREATE TABLE raw_customers (id INT)"

# Executar arquivo de tarefa versionado
data-agent run tasks/sql/review_query_pedidos.yaml
data-agent run tasks/spark/scd2_clientes.md
data-agent run tasks/pipelines/              # pasta inteira

# Utilitários
data-agent health    # status das plataformas
data-agent list      # agentes disponíveis
data-agent tasks     # arquivos em tasks/

# Interface web Chainlit
make ui

# Evals
make evals                         # todas as queries
make evals-domain DOMAIN=sql       # por domínio
```

Ver [QUICK_START.md](QUICK_START.md) para guia completo incluindo formato dos arquivos de tarefa.

---

## 🤖 Agentes e Comandos

| Comando | Agente | Domínio |
|---------|--------|---------|
| `/plan <tarefa>` | Supervisor | Tarefas complexas com PRD |
| `/spark <tarefa>` | Spark Expert | PySpark, Delta Lake, DLT |
| `/sql <tarefa>` | SQL Expert | Queries, modelagem, Unity Catalog |
| `/pipeline <tarefa>` | Pipeline Architect | ETL/ELT |
| `/quality <tarefa>` | Data Quality | Validação, DQX, profiling |
| `/naming <tarefa>` | Naming Guard | Auditoria de nomenclatura |
| `/governance <tarefa>` | Governance Auditor | PII, LGPD, controles |
| `/dbt <tarefa>` | dbt Expert | Models, snapshots, incremental |
| `/python <tarefa>` | Python Expert | Código Python, testes |
| `/fabric <tarefa>` | Fabric Expert | Lakehouse, OneLake, Direct Lake |
| `/lakehouse <tarefa>` | Lakehouse Engineer | Implantação, migração |
| `/ops <tarefa>` | Lakehouse Engineer | Manutenção, incidente, custo |
| `/ai <tarefa>` | Databricks AI | Agent Bricks, Genie, MLflow |
| `/devops <tarefa>` | DevOps Engineer | DABs, Azure DevOps, Fabric CI/CD |
| `/geral <tarefa>` | Geral | Conceitual, sem MCP |
| `/review <artefato>` | Supervisor | Review de código/pipeline |
| `/party <tarefa>` | Party Mode | Multi-agente paralelo |
| `/assessment [--days N]` | fabricgov + Governance Auditor | Assessment Fabric |
| `/health` | — | Status de conectividade |
| `/kg list\|lineage\|add` | — | Knowledge Graph |
| `/sessions` | — | Histórico de sessões |
| `/resume [task]` | — | Retomar última sessão |


**Auto-triggers** (sem comando):
- `CREATE TABLE / ALTER TABLE / DROP TABLE` → Naming Guard
- `pipeline`, `bronze`, `silver`, `gold`, `lakehouse`, `fabric`... → PRD + delegação
- Padrões de workflow → WF-01 a WF-07 encadeados

---

## ⚙️ Workflows Colaborativos

| ID | Trigger | Etapas |
|----|---------|--------|
| WF-01 | `pipeline completo, end-to-end, bronze até gold` | 2 agentes |
| WF-02 | `star schema, camada gold, modelo dimensional` | 3 agentes |
| WF-03 | `migrar para Fabric / Databricks` | 3 agentes |
| WF-04 | `auditoria, governança completa, compliance` | 3 agentes |
| WF-05 | `implantar lakehouse, novo lakehouse, setup lakehouse` | 5 agentes |
| WF-06 | `migrar lakehouse, migrar Synapse` | 6 agentes |
| WF-07 | `sustentação, otimizar lakehouse, vacuum, observabilidade` | 4 agentes |

---

## 🔐 Segurança & Governança

### Políticas Separadas

```python
# Input do usuário — bloqueia destrutivos + queries não qualificadas
ok, reason = security_hook.check_input(user_input)

# Output de agente — bloqueia só destrutivos reais (não bloqueia docs SQL)
ok, reason = security_hook.check_output(agent_result.content)
```

Padrões bloqueados no **input**: `DROP TABLE`, `TRUNCATE`, `rm -rf`, `git push --force`, `.env`, `.ssh/`, `DELETE FROM` sem WHERE, `SELECT *` sem WHERE/LIMIT.

Padrões bloqueados no **output**: apenas os destrutivos — agentes podem gerar documentação com `SELECT *` normalmente.

---

## 🧪 Testes

```bash
GITHUB_TOKEN=test pytest tests/ -v --cov --cov-fail-under=80
```

233 testes, cobertura 83%, ruff=0.

---

## 🏗️ Arquitetura

Ver [ARCHITECTURE.md](ARCHITECTURE.md) para diagramas de sistema, fluxo de roteamento e decisões de design.

---

## 📚 Documentação

- [Agentes](agents/registry/) — System prompts, tiers, skills, MCPs
- [Arquitetura](ARCHITECTURE.md) — Diagramas e decisões de design
- [Convenções de Nomenclatura](resources/naming%20convention.md) — Editável, fonte de verdade
- [Knowledge Base](kb/) — 18 domínios + constitution

### Documentação canônica do upstream

Para entender o sistema original (mais maduro e completo):

- [Repositório upstream](https://github.com/ThomazRossito/data-agents)
- [Manual Técnico Completo (upstream)](https://github.com/ThomazRossito/data-agents/blob/main/Manual_Relatorio_Tecnico_Projeto_Data_Agents.md)
- [PRODUCT.md (upstream)](https://github.com/ThomazRossito/data-agents/blob/main/PRODUCT.md)

---

## 🤝 Contribuindo

Ver [CONTRIBUTING.md](CONTRIBUTING.md). Para contribuições significativas em arquitetura ou novos agentes, considere abrir issue/PR diretamente no [upstream](https://github.com/ThomazRossito/data-agents) — esse fork tende a permanecer enxuto e focado em uso pessoal.

---

## 📄 Licença

Fork de [ThomazRossito/data-agents](https://github.com/ThomazRossito/data-agents) — MIT License. Crédito e atribuição ao autor original. Ver [LICENSE.md](LICENSE.md).
