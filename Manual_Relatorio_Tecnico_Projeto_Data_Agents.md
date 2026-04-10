# Manual e Relatorio Tecnico: Projeto Data Agents v3.1

---

Repositorio:  [github.com/ThomazRossito/data-agents](https://github.com/ThomazRossito/data-agents)

---

## Autor

> ## Thomaz Antonio Rossito Neto
>
> Specialist Data & AI Solutions Architect | Center of Excellence CoE @CI&T | Enterprise AI Agents, Microsoft Fabric & Databricks Expert

## Educacao Academica

> **MBA: Ciencia de Dados com enfase em Big Data**

> **MBA: Engenharia de Dados com enfase em Big Data**

## Contatos

> **LinkedIn:** [https://www.linkedin.com/in/thomaz-antonio-rossito-neto/](https://www.linkedin.com/in/thomaz-antonio-rossito-neto/)

> **GitHub:** [https://github.com/ThomazRossito/](https://github.com/ThomazRossito/)

---

#### Profissional Certificado Databricks

<img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/125134719" alt="Databricks Certified Spark Developer" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/169321258" alt="Databricks Certified Generative AI Engineer Associate" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/167127257" alt="Databricks Certified Data Analyst Associate" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/125134780" alt="Databricks Certified Data Engineer Associate" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/157011932" alt="Databricks Certified Data Engineer Professional" width="155"/>

[Todas as certificacoes](https://credentials.databricks.com/profile/thomazantoniorossitoneto39867/wallet)

---

#### Profissional Certificado Microsoft

<a href="https://www.credly.com/badges/052e5133-0c67-4ab7-bb3a-c99efa7b4406/public_url" target="_blank">
  <img src="https://images.credly.com/images/70eb1e3f-d4de-4377-a062-b20fb29594ea/azure-data-fundamentals-600x600.png" alt="Microsoft Certified: Azure Data Fundamentals (DP-900)" width="155"/>
</a>
<a href="https://learn.microsoft.com/pt-br/users/thomazantoniorossitoneto/credentials/certification/fabric-data-engineer-associate" target="_blank">
  <img src="https://files.manuscdn.com/user_upload_by_module/session_file/310419663028569643/ftqfVZsrmaGyfUha.png" alt="Microsoft Certified: Fabric Data Engineer Associate (DP-700)" width="155"/>
</a>

[Todas as certificacoes](https://www.credly.com/users/thomaz-antonio-rossito-neto/badges#credly)

---

## Sumario

1. [O que e este projeto?](#1-o-que-e-este-projeto)
2. [Conceitos Fundamentais (Glossario)](#2-conceitos-fundamentais-glossario)
3. [Arquitetura Geral do Sistema](#3-arquitetura-geral-do-sistema)
4. [Os Agentes: A Equipe Virtual](#4-os-agentes-a-equipe-virtual)
5. [O Metodo BMAD, KB-First e Constituicao](#5-o-metodo-bmad-kb-first-e-constituicao)
6. [Estrutura de Arquivos e Pastas](#6-estrutura-de-arquivos-e-pastas)
7. [Analise Detalhada de Cada Componente](#7-analise-detalhada-de-cada-componente)
8. [Seguranca e Controle de Custos (Hooks)](#8-seguranca-e-controle-de-custos-hooks)
9. [O Hub de Conhecimento (KBs, Skills e Constituicao)](#9-o-hub-de-conhecimento-kbs-skills-e-constituicao)
10. [Workflows Colaborativos e Spec-First](#10-workflows-colaborativos-e-spec-first)
11. [Conexoes com a Nuvem (MCP Servers)](#11-conexoes-com-a-nuvem-mcp-servers)
12. [Comandos Disponiveis (Slash Commands)](#12-comandos-disponiveis-slash-commands)
13. [Configuracao e Credenciais](#13-configuracao-e-credenciais)
14. [Checkpoint de Sessao (Recuperacao Automatica)](#14-checkpoint-de-sessao-recuperacao-automatica)
15. [Qualidade de Codigo e Testes](#15-qualidade-de-codigo-e-testes)
16. [Deploy e CI/CD (Publicacao Automatica)](#16-deploy-e-cicd-publicacao-automatica)
17. [Dashboard de Monitoramento](#17-dashboard-de-monitoramento)
18. [Como Comecar a Usar](#18-como-comecar-a-usar)
19. [Historico de Melhorias (v3.0 e v3.1)](#19-historico-de-melhorias-v30-e-v31)
20. [Conclusao](#20-conclusao)

---

## 1. O que e este projeto?

O **Data Agents** e um sistema avancado de **multiplos agentes de Inteligencia Artificial** projetado para atuar como uma equipe completa e autonoma nas areas de Engenharia de Dados, Qualidade de Dados, Governanca e Analise Corporativa.

Se voce ja usou o ChatGPT ou o Claude para pedir ajuda com codigo, imagine dar um passo alem: em vez de apenas responder perguntas, esta IA possui acesso direto ao seu ambiente na nuvem (Databricks e Microsoft Fabric) para executar as tarefas por voce, de ponta a ponta.

O diferencial do Data Agents e que a IA opera sob uma **Constituicao** — um documento central com regras inviolaveis — e uma **camada declarativa de governanca e conhecimento**. Isso significa que a IA e rigorosamente obrigada a ler as regras de negocio da sua empresa (Knowledge Bases) e os manuais tecnicos oficiais (Skills) *antes* de planejar ou executar qualquer acao. O resultado e um codigo nao apenas funcional, mas seguro, auditavel e perfeitamente alinhado com a arquitetura corporativa moderna.

Na versao 3.1, o sistema tambem conta com **Workflows Colaborativos** (cadeias automaticas de agentes), **Checkpoint de Sessao** (recuperacao automatica quando o orcamento estoura) e um **Dashboard de Monitoramento** com 9 paginas e filtro de datas.

---

## 2. Conceitos Fundamentais (Glossario)

Para garantir que este manual seja compreensivel mesmo para quem nao e especialista em Inteligencia Artificial, preparamos este glossario com os termos essenciais.

| Termo Tecnico | O que significa na pratica |
|---|---|
| **Agente de IA** | Um programa inteligente que nao apenas conversa, mas toma decisoes, planeja passos, usa ferramentas e executa tarefas de forma autonoma. |
| **LLM (Large Language Model)** | O "cerebro" por tras da IA. Neste projeto, utilizamos a familia de modelos **Claude** (da Anthropic), conhecida por excelencia em raciocinio logico e programacao. |
| **MCP (Model Context Protocol)** | Protocolo de codigo aberto que permite que a IA se conecte de forma segura a sistemas externos (bancos de dados, nuvens) para realizar acoes reais. Funciona como uma "tomada universal". |
| **Databricks** | Plataforma de dados em nuvem especializada em processar volumes massivos de informacoes usando Apache Spark. |
| **Microsoft Fabric** | Plataforma de dados unificada da Microsoft que junta armazenamento (OneLake), engenharia (Data Factory), analise em tempo real (RTI) e visualizacao (Power BI). |
| **Apache Spark / PySpark** | Tecnologia para processamento de Big Data que distribui trabalho entre dezenas de computadores. PySpark e a versao usando Python. |
| **Arquitetura Medallion** | Padrao da industria para organizar dados em tres camadas: **Bronze** (dados brutos), **Silver** (dados limpos) e **Gold** (dados prontos para relatorios). |
| **Knowledge Base (KB)** | Arquivos que contem as **regras de negocio e padroes arquiteturais** da empresa. A IA le isso para saber *o que* deve ser feito. |
| **Skills** | Manuais operacionais detalhados. Enquanto a KB diz *o que* fazer, a Skill ensina *como* usar uma tecnologia especifica. |
| **Constituicao** | Documento de autoridade maxima do sistema (`kb/constitution.md`). Contem ~50 regras inviolaveis que prevalecem sobre qualquer instrucao do usuario. |
| **Clarity Checkpoint** | Etapa de validacao onde o Supervisor pontua a clareza da requisicao em 5 dimensoes antes de prosseguir. Minimo 3/5 para continuar. |
| **Workflow Colaborativo** | Cadeia automatica de agentes que trabalham em sequencia, passando contexto entre si (ex: SQL Expert gera schema, Spark Expert transforma, Quality valida). |
| **Checkpoint de Sessao** | Ponto de salvamento automatico do estado da sessao. Permite retomar o trabalho apos um estouro de orcamento ou reset, sem perder o progresso. |
| **Hook** | "Gancho" de seguranca que monitora tudo que a IA tenta fazer. Se tentar algo perigoso, o Hook intercepta e bloqueia. |
| **PRD (Product Requirements Document)** | Documento de arquitetura criado pelo Supervisor antes de delegar, detalhando exatamente o que sera construido. |
| **Registry de Agentes** | Pasta (`agents/registry/`) onde agentes sao definidos em arquivos Markdown. Nao e necessario programar em Python para criar um novo agente. |

---

## 3. Arquitetura Geral do Sistema

A arquitetura do Data Agents v3.1 e hierarquica, segura e extensivel. O fluxo de trabalho funciona de maneira semelhante a uma equipe humana em uma empresa.

### O Fluxo de Trabalho

1. **A Interface (O Terminal):** Voce digita um pedido no terminal (ex: `/plan Crie um pipeline de vendas no Databricks`). O arquivo `main.py` recebe esse pedido.
2. **O Gerente (Supervisor):** O pedido vai para o **Data Orchestrator** (Supervisor). Ele le a Constituicao e as regras da empresa (KBs), executa o Clarity Checkpoint para validar se a requisicao esta clara, desenha o plano arquitetural (PRD) e decide qual especialista acionar.
3. **A Equipe (Especialistas):** O Supervisor aciona os agentes especialistas. Eles recebem a tarefa, leem os manuais tecnicos (Skills) e comecam a trabalhar. Em tarefas complexas, podem trabalhar em cadeia via Workflows Colaborativos.
4. **A Ponte (MCP Servers):** Para fazer o trabalho real na nuvem, os especialistas enviam comandos atraves dos servidores MCP, que traduzem a intencao da IA em acoes concretas no Databricks ou Fabric.
5. **Os Guardioes (Hooks):** O tempo todo, 7 Hooks de seguranca e auditoria observam silenciosamente, registram cada acao e bloqueiam comandos que violem as regras.

### Diagrama da Arquitetura

<p align="center">
  <img src="img/readme/architecture_v2.png" alt="Arquitetura Multi-Agent System" width="100%">
</p>

---

## 4. Os Agentes: A Equipe Virtual

O projeto conta com **6 agentes especialistas** divididos em dois niveis de atuacao (Tiers), mais o Supervisor. Todos sao definidos em arquivos Markdown na pasta `agents/registry/`, tornando facil adicionar novos membros a equipe.

### O Supervisor (Data Orchestrator)

- **Onde vive:** `agents/supervisor.py` + `agents/prompts/supervisor_prompt.py`
- **Modelo de IA:** `claude-opus-4-6` (o mais avancado, focado em raciocinio complexo)
- **O que faz:** E o gerente do projeto. Ele nao escreve codigo — seu trabalho e ler a Constituicao e as KBs, executar o Clarity Checkpoint, criar PRDs, delegar tarefas e validar os resultados contra as regras constitucionais.
- **Novidade v3.1:** Executa o Clarity Checkpoint (Passo 0.5) para validar a clareza da requisicao, suporta Workflows Colaborativos (WF-01 a WF-04) e faz Validacao Constitucional no Passo 4.

### Tier 1 — Engenharia de Dados (O Core)

#### 1. SQL Expert (`/sql`)
- **Modelo:** `claude-sonnet-4-6`
- **Analogia:** O Analista de Dados e DBA.
- **O que faz:** Escreve e otimiza consultas SQL (Spark SQL, T-SQL, KQL). Descobre estrutura de tabelas, explora Unity Catalog e gera codigo para criar tabelas.
- **Seguranca:** Permissao de **leitura e escrita de arquivos** (pode gravar `.sql`), mas acesso **read-only** a nuvem.

#### 2. Spark Expert (`/spark`)
- **Modelo:** `claude-sonnet-4-6`
- **Analogia:** O Desenvolvedor Back-end de Big Data.
- **O que faz:** Mestre em Python e Apache Spark. Escreve codigo PySpark para transformar dados, pipelines SDP e Delta Lake.
- **Seguranca:** **Nao tem acesso a nuvem** (sem MCP). Recebe um problema e devolve codigo Python.

#### 3. Pipeline Architect (`/pipeline` e `/fabric`)
- **Modelo:** `claude-opus-4-6`
- **Analogia:** O Engenheiro Cloud e DevOps.
- **O que faz:** Orquestra execucao na nuvem: cria Jobs no Databricks, monta Pipelines no Data Factory, move arquivos entre plataformas.
- **Seguranca:** Unico agente de engenharia com permissoes de **execucao e escrita**. Fortemente monitorado pelos Hooks.

### Tier 2 — Qualidade, Governanca e Analise

#### 4. Data Quality Steward (`/quality`)
- **Modelo:** `claude-sonnet-4-6`
- **Analogia:** O Engenheiro de Qualidade (QA).
- **O que faz:** Analisa tabelas para encontrar anomalias (*data profiling*), escreve regras de validacao (*expectations*) e configura alertas em tempo real no Fabric Activator.

#### 5. Governance Auditor (`/governance`)
- **Modelo:** `claude-sonnet-4-6`
- **Analogia:** O Auditor de Compliance e Seguranca.
- **O que faz:** Rastreia linhagem de dados, audita acessos, varre bancos procurando informacoes sensiveis (CPFs, e-mails) e garante conformidade LGPD/GDPR.

#### 6. Semantic Modeler (`/semantic`)
- **Modelo:** `claude-sonnet-4-6`
- **Analogia:** O Especialista de BI.
- **O que faz:** Constroi modelos semanticos DAX (Power BI), otimiza tabelas Gold para Direct Lake e configura Metric Views no Databricks.

---

## 5. O Metodo BMAD, KB-First e Constituicao

### A Constituicao

A versao 3.1 introduziu o conceito de **Constituicao** (`kb/constitution.md`) — um documento central com ~50 regras inviolaveis, dividido em 8 secoes:

1. **Principios Fundamentais (P1-P5):** KB-First obrigatorio, Spec-First para tarefas complexas, delegacao especializada, auditoria total, menor privilegio.
2. **Regras do Supervisor (S1-S7):** Nunca gerar codigo, sempre consultar KB, sempre validar contra a Constituicao.
3. **Clarity Checkpoint:** 5 dimensoes de avaliacao.
4. **Regras de Arquitetura:** Medallion (Bronze/Silver/Gold) e Star Schema (SS1-SS5).
5. **Regras de Plataforma:** Databricks (DB1-DB5) e Fabric (FB1-FB5).
6. **Seguranca (SEC1-SEC6):** Sem credenciais hardcoded, PII protegido, menor privilegio.
7. **Qualidade (QA1-QA6):** Expectations obrigatorios, profiling antes de promover.
8. **Modelagem Semantica (SM1-SM6):** Direct Lake, DAX, Metric Views.

Se houver conflito entre uma instrucao do usuario e a Constituicao, **a Constituicao prevalece**.

### A Filosofia KB-First

A regra de ouro: **a IA nunca adivinha, ela le o manual.** Antes de comecar a trabalhar, a IA e forcada a ler as Knowledge Bases (`kb/`) da empresa.

### O Clarity Checkpoint (Passo 0.5)

Antes de planejar tarefas complexas, o Supervisor pontua a clareza da requisicao em 5 dimensoes:

| Dimensao | O que avalia |
|----------|-------------|
| **Objetivo** | O resultado esperado e compreensivel? |
| **Escopo** | As tabelas, schemas e plataformas estao definidos? |
| **Plataforma** | E Databricks, Fabric ou ambos? |
| **Criticidade** | E exploracao, desenvolvimento ou producao? |
| **Dependencias** | As dependencias estao documentadas? |

**Pontuacao minima: 3/5.** Se < 3, o Supervisor pede esclarecimentos antes de prosseguir.

### Os Passos do Protocolo BMAD

```
Passo 0   - KB-First: le Knowledge Bases relevantes ao tipo de tarefa
Passo 0.5 - Clarity Checkpoint: valida clareza (5 dimensoes, minimo 3/5)
Passo 0.9 - Spec-First: seleciona template de spec para tarefas complexas (3+ agentes)
Passo 1   - Planejamento: cria PRD em output/ com a arquitetura da solucao
Passo 2   - Aprovacao: mostra resumo e aguarda confirmacao do usuario
Passo 3   - Delegacao: aciona agentes (com suporte a Workflows Colaborativos)
Passo 4   - Sintese e Validacao Constitucional: verifica aderencia a kb/constitution.md
```

### Modos de Velocidade

- **BMAD Full (`/plan`):** Fluxo completo, ideal para pipelines inteiros. Usa thinking avancado.
- **BMAD Express (`/sql`, `/quality`, etc.):** Pula planejamento, vai direto ao especialista. Rapido e barato.
- **Internal (`/health`, `/status`, `/review`):** Diagnosticos do sistema.

---

## 6. Estrutura de Arquivos e Pastas

```text
data-agents/
+-- agents/
|   +-- registry/               # Agentes definidos em Markdown
|   |   +-- _template.md        # Molde para novos agentes
|   |   +-- sql-expert.md
|   |   +-- spark-expert.md
|   |   +-- pipeline-architect.md
|   |   +-- data-quality-steward.md
|   |   +-- governance-auditor.md
|   |   +-- semantic-modeler.md
|   +-- loader.py               # Motor que transforma .md em agentes vivos
|   +-- prompts/
|   |   +-- supervisor_prompt.py # Prompt do Supervisor (com Clarity Checkpoint e Workflows)
|   +-- supervisor.py           # Factory do ClaudeAgentOptions
+-- commands/
|   +-- parser.py               # Slash commands (/plan, /sql, /spark, etc.)
+-- config/
|   +-- exceptions.py           # Erros personalizados (BudgetExceededError, etc.)
|   +-- logging_config.py       # Logging estruturado JSONL + console separado
|   +-- mcp_servers.py          # Registry de conexoes MCP
|   +-- settings.py             # Configuracoes via Pydantic BaseSettings
+-- hooks/
|   +-- audit_hook.py           # Log JSONL com categorizacao de erros (6 categorias)
|   +-- checkpoint.py           # Checkpoint de sessao (save/load/resume)
|   +-- cost_guard_hook.py      # Classificacao HIGH/MEDIUM/LOW de custos
|   +-- output_compressor_hook.py # Trunca outputs MCP (economia de tokens)
|   +-- security_hook.py        # Bloqueia comandos destrutivos e SQL custoso
|   +-- session_logger.py       # Metricas de custo/turnos/duracao por sessao
|   +-- workflow_tracker.py     # Rastreia delegacoes, workflows e Clarity Checkpoint
+-- kb/                         # Knowledge Bases (Regras da Empresa)
|   +-- constitution.md         # Documento de autoridade maxima (~50 regras)
|   +-- collaboration-workflows.md # Workflows Colaborativos (WF-01 a WF-04)
|   +-- README.md               # Indice geral das KBs
|   +-- data-quality/           # Regras de qualidade
|   +-- databricks/             # Padroes Databricks
|   +-- fabric/                 # Padroes Fabric
|   +-- governance/             # Regras de governanca
|   +-- pipeline-design/        # Padroes de pipeline
|   +-- semantic-modeling/      # Modelagem semantica
|   +-- spark-patterns/         # Padroes Spark
|   +-- sql-patterns/           # Padroes SQL
+-- templates/                  # Templates Spec-First
|   +-- pipeline-spec.md        # Template para pipelines ETL/ELT
|   +-- star-schema-spec.md     # Template para Star Schema (Gold)
|   +-- cross-platform-spec.md  # Template para Fabric <-> Databricks
|   +-- README.md
+-- mcp_servers/                # Configuracoes dos MCP Servers
|   +-- databricks/
|   +-- fabric/
|   +-- fabric_rti/
+-- skills/                     # Manuais Operacionais
|   +-- databricks/ (27 modulos)
|   +-- fabric/ (5 modulos)
+-- monitoring/
|   +-- app.py                  # Dashboard Streamlit (9 paginas)
+-- logs/                       # Logs gerados automaticamente
|   +-- audit.jsonl             # Todas as tool calls
|   +-- app.jsonl               # Eventos internos
|   +-- sessions.jsonl          # Custo/turnos por sessao
|   +-- workflows.jsonl         # Delegacoes, workflows, Clarity Checkpoint
|   +-- compression.jsonl       # Metricas do output compressor
|   +-- checkpoint.json         # Estado da ultima sessao (para recovery)
+-- tests/                      # Testes automatizados
+-- main.py                     # Entrada principal
+-- pyproject.toml              # Dependencias e configuracao
+-- .env.example                # Molde para credenciais
```

---

## 7. Analise Detalhada de Cada Componente

### O Arquivo Principal (`main.py`)

Quando voce digita `python main.py` no terminal, este arquivo exibe o banner, verifica credenciais, inicia o loop interativo e gerencia o ciclo de vida da sessao.

**Novidades da v3.1:** O main.py agora gerencia um **estado de sessao** (`_session_state`) que rastreia o ultimo prompt, custo acumulado e turns. Esse estado e usado para salvar checkpoints automaticos quando o budget estoura, o usuario reseta a sessao ou ocorre idle timeout. Na inicializacao, ele verifica se existe um checkpoint anterior e oferece a opcao de retomar.

### O Motor de Agentes (`loader.py` e `registry/`)

O `loader.py` le todos os arquivos Markdown em `agents/registry/`, extrai o frontmatter YAML e transforma cada arquivo em um agente vivo. Para criar um agente novo, basta copiar `_template.md`, personalizar e salvar.

Capacidades do loader: lazy-loading de KBs por dominio (`kb_domains`), Model Routing por Tier (`tier_model_map`), filtragem automatica de MCP servers indisponiveis e resolucao de aliases de tools (ex: `databricks_readonly` vira a lista completa de tools de leitura).

### O Configurador (`settings.py`)

Painel de controle via Pydantic BaseSettings, com todas as variaveis carregadas do `.env`:

- **`default_model`**: Modelo padrao (`claude-opus-4-6`)
- **`max_budget_usd`**: Limite de custo por sessao (padrao: `$5.00`)
- **`max_turns`**: Limite de turns (padrao: `50`)
- **`console_log_level`**: Nivel de log no terminal (padrao: `WARNING` — esconde logs operacionais)
- **`tier_model_map`**: Override de modelo por tier
- **`inject_kb_index`**: Injecao automatica de KBs nos agentes
- **`idle_timeout_minutes`**: Reset automatico por inatividade (padrao: `30`)

---

## 8. Seguranca e Controle de Custos (Hooks)

O Data Agents possui **7 Hooks** especializados, organizados em camadas. Hooks sao filtros invisiveis pelos quais todo comando da IA precisa passar.

### Hooks PreToolUse (Executam ANTES da ferramenta)

#### O Seguranca (`security_hook.py` - `block_destructive_commands`)

Intercepta comandos Bash. Se a IA tentar rodar `DROP TABLE`, `DELETE FROM`, `rm -rf` ou qualquer dos 17 padroes destrutivos, o Hook bloqueia e forca outra abordagem. Tambem detecta 11 padroes de evasao (Base64, eval, variáveis de shell disfarçadas).

#### O Fiscal de Queries (`security_hook.py` - `check_sql_cost`)

Intercepta **todas** as ferramentas. Se encontrar um `SELECT *` sem `WHERE` e sem `LIMIT`/`TOP`, bloqueia para evitar full table scans acidentais. Detecta SQL embutido em Bash (spark-sql, beeline, databricks query).

### Hooks PostToolUse (Executam DEPOIS da ferramenta)

#### O Gravador (`audit_hook.py`)

Registra cada tool call em `logs/audit.jsonl` com timestamp, ferramenta, classificacao e chaves de input. **Novidade v3.1:** inclui **categorizacao automatica de erros** em 6 categorias (auth, timeout, rate_limit, mcp_connection, not_found, validation) e deteccao automatica de plataforma MCP.

#### O Rastreador de Workflows (`workflow_tracker.py`)

**Novidade v3.1.** Rastreia delegacoes de agentes, workflows colaborativos (WF-01 a WF-04), Clarity Checkpoint (score e resultado) e specs gerados. Grava eventos em `logs/workflows.jsonl`.

#### O Vigilante de Custos (`cost_guard_hook.py`)

Classifica cada ferramenta em LOW, MEDIUM ou HIGH. Se a IA fizer mais de 5 operacoes HIGH na mesma sessao, dispara alerta. Contadores sao resetados no idle timeout e no comando `limpar`.

#### O Compressor de Output (`output_compressor_hook.py`)

Filtra e trunca outputs MCP antes de chegarem ao modelo, economizando tokens:

| Tipo de Ferramenta | Limite | Exemplo |
|---|---|---|
| SQL/KQL | Max. 50 linhas | Resultado de SELECT |
| Listagens | Max. 30 itens | Lista de tabelas |
| Leitura de arquivos | Max. 200 linhas | Conteudo de notebook |
| Bash | Max. 100 linhas | Saida de comando |
| Qualquer outra | Max. 8.000 chars | Fallback generico |

Registrado como **ultimo** PostToolUse para que audit e cost_guard vejam o output original.

### Resumo dos Hooks

| Hook | Tipo | Protecao |
|------|------|----------|
| `block_destructive_commands` | PreToolUse (Bash) | 17 padroes destrutivos + 11 de evasao |
| `check_sql_cost` | PreToolUse (All) | Bloqueia SELECT * sem WHERE/LIMIT |
| `audit_hook` | PostToolUse | Log JSONL com 6 categorias de erro |
| `workflow_tracker` | PostToolUse | Delegacoes, workflows, Clarity Checkpoint |
| `cost_guard_hook` | PostToolUse | Custo HIGH/MEDIUM/LOW com alertas |
| `output_compressor_hook` | PostToolUse | Trunca outputs (SQL 50, listas 30, max 8K) |
| `checkpoint` | Budget/Reset | Salva estado para recuperacao automatica |

---

## 9. O Hub de Conhecimento (KBs, Skills e Constituicao)

O conhecimento do sistema e organizado em 3 camadas hierarquicas.

### Camada 1: A Constituicao (`kb/constitution.md`)

Documento de **autoridade maxima**. Contem ~50 regras inviolaveis que cobrem Medallion, Star Schema, seguranca, qualidade e plataformas. Se houver conflito com qualquer outra fonte, a Constituicao prevalece. O Supervisor a carrega no inicio de sessoes complexas.

### Camada 2: Knowledge Bases (`kb/`)

Regras de negocio e padroes arquiteturais, organizadas em 8 dominios:

| Dominio | Conteudo |
|---------|----------|
| `sql-patterns` | DDL, otimizacao, conversao de dialetos, Star Schema |
| `spark-patterns` | Delta Lake, SDP/LakeFlow, streaming, performance |
| `pipeline-design` | Medallion, orquestracao, cross-platform, Star Schema design |
| `data-quality` | Expectations, profiling, drift detection, SLAs, alertas |
| `governance` | Auditoria, linhagem, PII, compliance, controle de acesso |
| `semantic-modeling` | DAX, Direct Lake, Metric Views, reporting |
| `databricks` | Unity Catalog, compute, bundles, AI/ML, jobs |
| `fabric` | RTI, Eventhouse, Data Factory, Direct Lake |

Cada agente declara seus dominios em `kb_domains` e recebe apenas as KBs relevantes via lazy-loading.

### Camada 3: Skills Operacionais (`skills/`)

Manuais detalhados lidos pelos especialistas durante a execucao. 27 modulos Databricks e 5 modulos Fabric.

A separacao (Constituicao para regras absolutas, KBs para o Gerente, Skills para os Operarios) reduz a sobrecarga da IA e garante que o codigo final respeite a arquitetura da empresa e a sintaxe da ferramenta ao mesmo tempo.

---

## 10. Workflows Colaborativos e Spec-First

### Workflows Colaborativos

**Novidade v3.1.** Para tarefas que envolvem multiplos agentes, o sistema oferece 4 workflows pre-definidos em `kb/collaboration-workflows.md`:

| Workflow | Sequencia | Quando usar |
|----------|-----------|-------------|
| **WF-01: Pipeline End-to-End** | spark -> quality -> semantic -> governance | Pipeline completo Bronze-Gold |
| **WF-02: Star Schema** | sql -> spark -> quality -> semantic | Modelagem dimensional Gold |
| **WF-03: Cross-Platform** | pipeline -> sql -> spark -> quality + governance | Migracao Databricks <-> Fabric |
| **WF-04: Governance Audit** | governance -> quality -> relatorio | Auditoria completa |

Cada etapa recebe o contexto da etapa anterior via formato de handoff padronizado. Se um agente falhar, o workflow pausa e propoe correcao.

### Templates Spec-First

Para tarefas complexas (3+ agentes, 2+ plataformas), o Supervisor preenche um template de spec antes de delegar:

- `templates/pipeline-spec.md` — ETL/ELT com secoes Bronze/Silver/Gold e regras constitucionais
- `templates/star-schema-spec.md` — Star Schema com DAG, otimizacao e validacao
- `templates/cross-platform-spec.md` — Fabric <-> Databricks com mapeamento de dialetos

---

## 11. Conexoes com a Nuvem (MCP Servers)

O MCP permite que a IA interaja com o mundo real. O Data Agents possui 4 conexoes:

| Servidor | Plataforma | Tools | Capacidades |
|----------|-----------|-------|-------------|
| **Databricks** | Databricks | 31 | Unity Catalog, SQL, Pipelines SDP, Jobs |
| **Fabric** | Microsoft Fabric | 13 | Workspaces, Lakehouses, OneLake |
| **Fabric Community** | Microsoft Fabric | 27 | Tabelas, schemas, linhagem, jobs |
| **Fabric RTI** | Eventhouse / Kusto | ~15 | KQL, Eventstreams, Activator |

O arquivo `mcp_servers.py` detecta automaticamente quais plataformas tem credenciais validas e desliga as demais. Todas as credenciais sao gerenciadas via `.env` + pydantic-settings — **nenhum `export` manual no shell e necessario**.

O arquivo `.mcp.json` na raiz esta intencionalmente vazio para evitar conflitos de carregamento de credenciais.

---

## 12. Comandos Disponiveis (Slash Commands)

| Comando | O que faz | Modo | Quem executa |
|---------|----------|------|-------------|
| `/plan` | Fluxo completo com PRD e aprovacao | Full | Supervisor + Equipe |
| `/sql` | Tarefa SQL direto ao especialista | Express | SQL Expert |
| `/spark` | Codigo PySpark/Spark | Express | Spark Expert |
| `/pipeline` | Pipelines e infraestrutura | Express | Pipeline Architect |
| `/fabric` | Foco em Microsoft Fabric | Express | Pipeline Architect |
| `/quality` | Validacao e profiling | Express | Data Quality Steward |
| `/governance` | Auditoria e compliance | Express | Governance Auditor |
| `/semantic` | DAX, Direct Lake, metricas | Express | Semantic Modeler |
| `/health` | Verifica conectividade MCP | Internal | Sistema |
| `/status` | Lista PRDs em output/ | Internal | Sistema |
| `/review` | Revisita PRD existente | Internal | Sistema |
| `/help` | Mostra lista de comandos | Internal | Sistema |

### Controle de Sessao

| Comando | Funcao |
|---------|--------|
| `continuar` | Retoma sessao anterior a partir do checkpoint salvo |
| `limpar` | Reseta sessao atual (salva checkpoint antes) |
| `sair` | Encerra o Data Agents |

---

## 13. Configuracao e Credenciais

Crie um arquivo `.env` na raiz do projeto (use `.env.example` como base). **Nunca envie o `.env` para o GitHub** — o `.gitignore` ja protege contra isso.

### Obrigatorio

- **`ANTHROPIC_API_KEY`**: Chave da API da Anthropic.

### Databricks (opcional)

- **`DATABRICKS_HOST`**: URL do Databricks (ex: `https://adb-123456.azuredatabricks.net`)
- **`DATABRICKS_TOKEN`**: Personal Access Token
- **`DATABRICKS_SQL_WAREHOUSE_ID`**: ID do SQL Warehouse

### Microsoft Fabric (opcional)

- **`AZURE_TENANT_ID`**: ID do tenant Azure
- **`FABRIC_WORKSPACE_ID`**: ID do Workspace
- **`AZURE_CLIENT_ID`** e **`AZURE_CLIENT_SECRET`**: Service Principal

### Fabric RTI (opcional)

- **`KUSTO_SERVICE_URI`**: URL do Eventhouse
- **`KUSTO_SERVICE_DEFAULT_DB`**: Database padrao

### Configuracoes do Sistema

| Variavel | Padrao | Descricao |
|----------|--------|-----------|
| `MAX_BUDGET_USD` | 5.0 | Limite de custo por sessao em dolares |
| `MAX_TURNS` | 50 | Limite de turns por sessao |
| `LOG_LEVEL` | INFO | Nivel de log para o arquivo JSONL |
| `CONSOLE_LOG_LEVEL` | WARNING | Nivel de log no terminal (WARNING esconde logs operacionais como OUTPUT COMPRIMIDO) |
| `TIER_MODEL_MAP` | {} | Override de modelo por tier. Ex: `'{"T1": "claude-opus-4-6", "T2": "claude-haiku-3-5"}'` |
| `INJECT_KB_INDEX` | true | Injecao automatica de KBs |
| `IDLE_TIMEOUT_MINUTES` | 30 | Reset automatico por inatividade (0 para desabilitar) |

---

## 14. Checkpoint de Sessao (Recuperacao Automatica)

**Novidade v3.1.** Um dos maiores problemas ao trabalhar com agentes de IA e a perda de contexto quando o orcamento estoura no meio de uma tarefa complexa. O sistema de Checkpoint resolve isso.

### Como funciona

O sistema mantem um **estado de sessao** que rastreia o ultimo prompt enviado, custo acumulado e numero de turns. Quando ocorre uma interrupcao, esse estado e salvo automaticamente em `logs/checkpoint.json` junto com a lista de arquivos gerados em `output/`.

### Quando o checkpoint e salvo automaticamente

1. **Budget excedido (BudgetExceededError):** O orcamento da sessao estourou. O checkpoint e salvo e o terminal exibe uma mensagem orientando o usuario a digitar `continuar` na proxima sessao.
2. **Reset pelo usuario (`limpar`):** O usuario reseta a sessao. O progresso e salvo antes da limpeza.
3. **Idle timeout:** A sessao ficou inativa alem do limite configurado.

### Como retomar

Na proxima sessao, o sistema detecta o checkpoint e exibe um painel com detalhes (custo, ultimo prompt, arquivos gerados). Digite **`continuar`** para retomar. O sistema monta automaticamente um prompt de contexto com todo o estado anterior e injeta no Supervisor, que le os arquivos de `output/` e identifica o que foi feito e o que falta.

Se preferir comecar do zero, basta digitar qualquer outro comando — o checkpoint e descartado.

---

## 15. Qualidade de Codigo e Testes

O projeto mantem uma bateria de testes automatizados na pasta `tests/` com cobertura minima de **80%**.

### Como rodar

```bash
make lint      # ruff check + ruff format
make test      # pytest com cobertura
```

### O que os testes verificam

1. **Loader Dinamico (`test_agents.py`):** Parser YAML, resolucao de tools, Model Routing por Tier, injecao de KBs.
2. **Seguranca (`test_hooks.py`):** Bloqueio de comandos destrutivos, check_sql_cost, cost_guard.
3. **Compressor (`test_output_compressor.py`):** Truncamento por tipo de ferramenta.
4. **Parser (`test_commands.py`):** Slash commands e roteamento.
5. **MLflow (`test_mlflow_wrapper.py`):** Servimento de modelos.
6. **Logging (`test_logging_config.py`):** JSONLFormatter, setup_logging.
7. **Supervisor (`test_supervisor.py`):** build_supervisor_options, hooks configurados.
8. **Settings (`test_settings.py`):** Validacao de credenciais, defaults.
9. **MCP (`test_mcp_configs.py`):** Configs de Databricks e Fabric.

---

## 16. Deploy e CI/CD (Publicacao Automatica)

### CI (Integracao Continua)

Dispara em push/PR para `main`/`develop`. Tres pipelines em paralelo:

1. **Code Quality:** ruff check + ruff format + mypy (verificacao de tipos)
2. **Tests:** pytest com cobertura minima 80%
3. **Security:** bandit para detectar vulnerabilidades

### CD (Deploy Continuo)

Dispara em tags. Deploy automatico via Databricks Asset Bundles para staging/production.

### Pre-commit Hooks

O projeto usa pre-commit hooks locais que rodam automaticamente antes de cada commit: ruff, ruff-format, trailing-whitespace, end-of-file-fixer, bandit. Se o commit falhar, os hooks corrigem os arquivos automaticamente — basta fazer stage novamente e commitar.

---

## 17. Dashboard de Monitoramento

### Instalacao e Inicio

```bash
pip install -e ".[monitoring]"
streamlit run monitoring/app.py
```

Abre em **http://localhost:8501**.

### As 9 Paginas do Dashboard

| Pagina | O que mostra |
|--------|-------------|
| **Overview** | KPIs gerais, atividade por data, top ferramentas, custo acumulado |
| **Agentes** | Cards dos 6 agentes + KPIs de performance (delegacoes, erros, taxa de erro) + erros por categoria |
| **Workflows** | Delegacoes por agente, workflows triggered (WF-01 a WF-04), Clarity Checkpoint (pass rate, score medio), specs gerados |
| **Execucoes** | Volume por ferramenta, chamadas MCP por plataforma, historico |
| **MCP Servers** | Status real baseado em chamadas do audit.jsonl |
| **Logs** | Viewer ao vivo do app.jsonl e audit.jsonl com filtros |
| **Configuracoes** | Modelo, budget, max_turns, mapa de arquivos do projeto |
| **Custo & Tokens** | Custo por sessao, por data, por tipo, economia do Output Compressor |
| **Sobre** | Autor, versao, licenca, arquitetura documentada |

### Funcionalidades Especiais

- **Filtro Global de Datas:** Seletor de periodo na sidebar que filtra todos os dados de todas as paginas.
- **Auto-refresh:** Atualizacao automatica a cada 5, 10, 30 ou 60 segundos.
- **Fuso Horario:** Todos os timestamps convertidos para Sao Paulo (UTC-3).

### Fontes de Dados

O dashboard le 5 arquivos de log:

- `logs/audit.jsonl` — todas as tool calls (gerado pelo `audit_hook.py`)
- `logs/app.jsonl` — eventos internos (gerado pelo `logging_config.py`)
- `logs/sessions.jsonl` — custo/turnos por sessao (gerado pelo `session_logger.py`)
- `logs/workflows.jsonl` — delegacoes e workflows (gerado pelo `workflow_tracker.py`)
- `logs/compression.jsonl` — metricas do compressor (gerado pelo `output_compressor_hook.py`)

---

## 18. Como Comecar a Usar

### Passo 1: Instale o Python 3.11+

### Passo 2: Baixe o Projeto

```bash
git clone https://github.com/ThomazRossito/data-agents.git
cd data-agents
```

### Passo 3: Instale as Dependencias

```bash
pip install -e ".[dev]"
```

### Passo 4: Configure suas Credenciais

```bash
cp .env.example .env
```

Edite o `.env` com suas chaves. A `ANTHROPIC_API_KEY` e obrigatoria.

### Passo 5: Inicie o Sistema

```bash
python main.py
```

Voce vera o banner do Data Agents e o prompt `Voce:`. Digite `/help` para ver os comandos ou escreva sua solicitacao em linguagem natural.

### Comandos uteis apos iniciar

- `/health` — verifica se as conexoes com a nuvem estao funcionando
- `/plan Crie um pipeline de vendas` — fluxo completo com planejamento
- `/sql Liste os catalogos do Databricks` — consulta rapida
- `continuar` — retoma sessao anterior (se houver checkpoint)
- `limpar` — reseta a sessao (salva checkpoint)

---

## 19. Historico de Melhorias (v3.0 e v3.1)

### Melhorias da v3.0

| Melhoria | Descricao |
|----------|-----------|
| Filtragem de outputs MCP | Hook output_compressor_hook.py que trunca por tipo de ferramenta |
| Model Routing por Tier | tier_model_map no loader.py permite override global de modelos |
| Lazy-loading de KB/Skills | Agentes recebem apenas KBs dos dominios declarados |
| check_sql_cost ativo | Bloqueia SELECT * sem WHERE/LIMIT em todas as tools |
| Reset automatico por idle | asyncio.wait_for com timeout configuravel |
| reset_session_counters | Contadores resetados em idle timeout e limpar |

### Melhorias da v3.1

| Melhoria | Descricao |
|----------|-----------|
| Constituicao centralizada | kb/constitution.md com ~50 regras inviolaveis em 8 secoes |
| Clarity Checkpoint | Passo 0.5 com scoring de 5 dimensoes (minimo 3/5) |
| Spec-First Templates | 3 templates em templates/ com regras constitucionais embutidas |
| Workflows Colaborativos | 4 workflows pre-definidos (WF-01 a WF-04) com handoff automatico |
| Checkpoint de Sessao | Save/resume automatico em budget exceeded, limpar e idle timeout |
| Workflow Tracker Hook | Rastreia delegacoes, workflows e Clarity Checkpoint em workflows.jsonl |
| Categorizacao de Erros | 6 categorias automaticas no audit_hook (auth, timeout, rate_limit, etc.) |
| Dashboard Workflows | Nova pagina com KPIs de delegacoes, clarity pass rate e specs |
| Dashboard Custo & Tokens | Pagina dedicada com economia do compressor |
| Filtro Global de Datas | Seletor de periodo na sidebar do dashboard |
| Console Log Level | Separacao de nivel console vs arquivo (WARNING esconde logs operacionais) |
| SQL Expert com Write | Corrigido — agora pode gravar arquivos .sql diretamente |

---

## 20. Conclusao

O projeto **Data Agents v3.1** e uma plataforma de automacao corporativa completa. Com a Constituicao como fonte de verdade, Clarity Checkpoint para validacao de requisicoes, Workflows Colaborativos para cadeias de agentes e Checkpoint de Sessao para resiliencia, o sistema cobre todo o ciclo de vida de dados — da ingestao na Bronze ate o modelo semantico para Power BI.

O ecossistema conta com 6 agentes especialistas, 7 hooks de protecao, 4 servidores MCP, 8 dominios de Knowledge Base, 32 modulos de Skills, 4 workflows pre-definidos e um dashboard de monitoramento com 9 paginas. Tudo isso definido declarativamente em Markdown e YAML, sem necessidade de programacao Python para estender.

Se a sua empresa precisar de um novo especialista amanha, basta criar um arquivo `.md` na pasta `registry/`. A fundacao ja esta construida.
