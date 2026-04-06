# Manual e Relatório Técnico: Projeto Data Agents v2.0

---

Repositório:  [github.com/ThomazRossito/data-agents](https://github.com/ThomazRossito/data-agents)

---

## 👤 Autor

> ## Thomaz Antonio Rossito Neto
>
> Specialist Data & AI Solutions Architect | Center of Excellence CoE @CI&T | Enterprise AI Agents, Microsoft Fabric & Databricks Expert

## Educação Acadêmica

> **MBA: Ciência de Dados com ênfase em Big Data**                           
> **MBA: Engenharia de Dados com ênfase em Big Data**

## Contatos

> **LinkedIn:** [https://www.linkedin.com/in/thomaz-antonio-rossito-neto/](https://www.linkedin.com/in/thomaz-antonio-rossito-neto/)                            
> **GitHub:** [https://github.com/ThomazRossito/](https://github.com/ThomazRossito/)

---

#### 🏆 Profissional Certificado Databricks

<img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/125134719" alt="Databricks Certified Spark Developer" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/169321258" alt="Databricks Certified Generative AI Engineer Associate" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/167127257" alt="Databricks Certified Data Analyst Associate" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/125134780" alt="Databricks Certified Data Engineer Associate" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/157011932" alt="Databricks Certified Data Engineer Professional" width="155"/>

[Todas as certificações](https://credentials.databricks.com/profile/thomazantoniorossitoneto39867/wallet)

---

#### 🏆 Profissional Certificado Microsoft

<a href="https://www.credly.com/badges/052e5133-0c67-4ab7-bb3a-c99efa7b4406/public_url" target="_blank">
  <img src="https://images.credly.com/images/70eb1e3f-d4de-4377-a062-b20fb29594ea/azure-data-fundamentals-600x600.png" alt="Microsoft Certified: Azure Data Fundamentals (DP-900)" width="155"/>
</a>
<a href="https://learn.microsoft.com/pt-br/users/thomazantoniorossitoneto/credentials/certification/fabric-data-engineer-associate" target="_blank">
  <img src="https://files.manuscdn.com/user_upload_by_module/session_file/310419663028569643/ftqfVZsrmaGyfUha.png" alt="Microsoft Certified: Fabric Data Engineer Associate (DP-700)" width="155"/>
</a>

[Todas as certificações](https://www.credly.com/users/thomaz-antonio-rossito-neto/badges#credly)

---

## Sumário

1. [O que é este projeto?](#1-o-que-é-este-projeto)
2. [Conceitos Fundamentais (Glossário para Iniciantes)](#2-conceitos-fundamentais-glossário-para-iniciantes)
3. [Arquitetura Geral do Sistema](#3-arquitetura-geral-do-sistema)
4. [Os Agentes: A Equipe Virtual](#4-os-agentes-a-equipe-virtual)
5. [O Método BMAD e KB-First](#5-o-método-bmad-e-kb-first)
6. [Estrutura de Arquivos e Pastas](#6-estrutura-de-arquivos-e-pastas)
7. [Análise Detalhada de Cada Componente](#7-análise-detalhada-de-cada-componente)
8. [Segurança e Controle de Custos (Hooks)](#8-segurança-e-controle-de-custos-hooks)
9. [O Hub de Conhecimento (KBs e Skills)](#9-o-hub-de-conhecimento-kbs-e-skills)
10. [Conexões com a Nuvem (MCP Servers)](#10-conexões-com-a-nuvem-mcp-servers)
11. [Comandos Disponíveis (Slash Commands)](#11-comandos-disponíveis-slash-commands)
12. [Configuração e Credenciais](#12-configuração-e-credenciais)
13. [Qualidade de Código e Testes](#13-qualidade-de-código-e-testes)
14. [Deploy e CI/CD (Publicação Automática)](#14-deploy-e-cicd-publicação-automática)
15. [Como Começar a Usar](#15-como-começar-a-usar)
16. [Conclusão](#16-conclusão)

---

## 1. O que é este projeto?

O **Data Agents** é um sistema de **múltiplos agentes de Inteligência Artificial** especializado em Engenharia de Dados, Qualidade, Governança e Análise Corporativa. Em termos simples, é como ter uma equipe completa de especialistas virtuais que trabalham juntos para resolver problemas complexos de dados.

O sistema é construído sobre o modelo de linguagem **Claude** da empresa Anthropic e utiliza a tecnologia **MCP (Model Context Protocol)** para que a IA possa interagir diretamente com plataformas de dados como Databricks e Microsoft Fabric.

O grande diferencial da versão 2.0 é a sua **camada declarativa de governança e conhecimento**. Os agentes não são mais classes Python rígidas, mas sim arquivos Markdown dinâmicos (Registry). Além disso, a IA é obrigada a ler manuais de boas práticas (Knowledge Bases e Skills) antes de agir, garantindo aderência estrita aos padrões corporativos modernos.

---

## 2. Conceitos Fundamentais (Glossário para Iniciantes)

| Termo | O que significa na prática |
| --- | --- |
| **Agente de IA** | Um programa de IA que pode tomar decisões, usar ferramentas e executar tarefas de forma autônoma. |
| **LLM (Large Language Model)** | O "cérebro" da IA. No caso deste projeto, é o Claude da Anthropic. |
| **MCP (Model Context Protocol)** | Uma "tomada universal" que permite que a IA se conecte a ferramentas externas de forma padronizada. |
| **Knowledge Base (KB)** | Arquivos que contêm as regras de negócio e padrões arquiteturais corporativos. Lidos *antes* do planejamento. |
| **Skills** | Manuais operacionais detalhados de ferramentas. Lidos *durante* a execução pelos agentes especialistas. |
| **Registry de Agentes** | Uma pasta (`agents/registry/`) contendo arquivos Markdown que definem os agentes do sistema. |
| **Databricks / Microsoft Fabric** | Plataformas de nuvem especializadas em processamento e análise de grandes volumes de dados. |
| **Pipeline de Dados** | Uma "linha de montagem" para dados (ex: arquitetura Medalhão Bronze/Silver/Gold). |
| **Hook** | Um "gancho" de código que intercepta as ações da IA para garantir segurança e auditar comandos. |
| **PRD** | *Product Requirements Document*. Um documento gerado pela IA descrevendo o que será construído. |

---

## 3. Arquitetura Geral do Sistema

O fluxo do sistema opera em uma topologia hierárquica (Supervisor → Especialistas) com injeção dinâmica de contexto:

```
 Você digita um comando no terminal (/plan, /sql, /quality)
        │
        ▼
┌─────────────────────────────────────────┐
│             main.py (Interface)         │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│        Supervisor (Data Orchestrator)   │
│  Lê KBs → Cria PRD → Delega tarefa      │
└──────┬──────────┬───────────────┬───────┘
       │          │               │
       ▼          ▼               ▼
 SQL Expert  Spark Expert   Pipeline Architect
 Quality Steward  Governance Auditor  Semantic Modeler
       │          │              │
       └──────────┴──────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│         MCP Servers (Pontes)            │
│  Databricks │ Fabric │ Fabric RTI       │
└─────────────────────────────────────────┘
                  │
                  ▼
         Plataformas de Nuvem Reais
```

Em paralelo a todo esse fluxo, os **Hooks** monitoram cada ação: bloqueando comandos destrutivos e registrando logs de auditoria.

<p align="center">
  <img src="img/readme/architecture.png" alt="Arquitetura Multi-Agent System" width="100%">
</p>

---

## 4. Os Agentes: A Equipe Virtual

A equipe é composta por **6 agentes especialistas** carregados dinamicamente pelo `loader.py` a partir da pasta `agents/registry/`.

### 4.1. O Supervisor (Data Orchestrator)
- **Modelo:** `claude-opus-4-6`
- **Papel:** O Gerente de Projetos Sênior. Ele recebe a requisição, lê as Knowledge Bases (KBs), elabora o PRD e delega a tarefa para o especialista correto.

### 4.2. SQL Expert (`/sql`)
- **Modelo:** `claude-sonnet-4-6`
- **Papel:** Especialista em banco de dados (KQL, T-SQL, Spark SQL). Analisa schemas Fato/Dimensão e gera DDLs otimizadas.

### 4.3. Spark Expert (`/spark`)
- **Modelo:** `claude-sonnet-4-6`
- **Papel:** Engenheiro de Big Data focado em geração de código PySpark e pipelines SDP/LakeFlow. Não acessa o MCP diretamente, foca em código.

### 4.4. Pipeline Architect (`/pipeline`)
- **Modelo:** `claude-opus-4-6`
- **Papel:** Arquiteto Cloud e DataOps. Orquestra Databricks Asset Bundles (DABs) e integrações cross-platform (Databricks ↔ Fabric).

### 4.5. Data Quality Steward (`/quality`)
- **Modelo:** `claude-sonnet-4-6`
- **Papel:** Guardião da saúde dos dados. Executa data profiling, define expectations, monitora SLAs e configura alertas no Fabric Activator.

### 4.6. Governance Auditor (`/governance`)
- **Modelo:** `claude-sonnet-4-6`
- **Papel:** Auditor de compliance. Mapeia linhagem de dados, identifica PII (dados sensíveis) e garante políticas LGPD/GDPR.

### 4.7. Semantic Modeler (`/semantic`)
- **Modelo:** `claude-sonnet-4-6`
- **Papel:** Analista de BI e Semântica. Cria modelos DAX, otimiza tabelas para Direct Lake e configura Databricks Metric Views e Genie.

---

## 5. O Método BMAD e KB-First

O **BMAD (Breakthrough Method for Agile AI-Driven Development)** é o protocolo de orquestração. A versão 2.0 introduziu a abordagem **KB-First**, que separa regras de negócio (KBs) de manuais de ferramentas (Skills).

1. **Passo 0 (Triage):** O Supervisor identifica o domínio da tarefa.
2. **Passo 1 (KB-First):** O Supervisor lê as Knowledge Bases (ex: `kb/pipeline-design/index.md`) para entender os padrões corporativos.
3. **Passo 2 (PRD):** O Supervisor escreve o plano de arquitetura e aguarda aprovação do usuário.
4. **Passo 3 (Delegação):** O Supervisor aciona o especialista via BMAD Express.
5. **Passo 4 (Skills):** O especialista lê as Skills operacionais (ex: `skills/databricks/databricks-spark-declarative-pipelines/SKILL.md`) e executa o código.

---

## 6. Estrutura de Arquivos e Pastas

```text
data-agents/
├── main.py                    # Entry point interativo
├── agents/
│   ├── loader.py              # Loader dinâmico de agentes YAML/Markdown
│   ├── registry/              # Definições dos agentes especialistas (.md)
│   ├── supervisor.py          # Orquestrador BMAD
│   └── prompts/               # Prompts base
├── kb/                        # 📚 Knowledge Bases (regras de negócio)
│   ├── data-quality/
│   ├── governance/
│   ├── pipeline-design/
│   └── ...
├── skills/                    # 📚 Manuais Operacionais (Databricks, Fabric)
├── commands/                  # Parser de slash commands (/sql, /quality)
├── hooks/                     # 🛡️ Camada de segurança (audit, cost, security)
├── config/                    # Configurações globais e MCP
├── mcp_servers/               # Configurações dos servidores MCP
├── tools/                     # Scripts de health check
└── tests/                     # Suíte de testes automatizados (pytest)
```

---

## 7. Análise Detalhada de Cada Componente

### 7.1. Loader Dinâmico (`agents/loader.py`)
Substituiu as antigas classes Python hardcoded. Ele lê os arquivos Markdown na pasta `registry/`, faz o parse do Frontmatter YAML e instancia os agentes com as ferramentas e modelos corretos.

### 7.2. O Parser de Comandos (`commands/parser.py`)
Gerencia os *Slash Commands*. Ele roteia o comando do usuário (ex: `/quality`) para o agente correto (`data-quality-steward`), aplicando o prompt template adequado e injetando o contexto necessário.

---

## 8. Segurança e Controle de Custos (Hooks)

O projeto implementa três ganchos (hooks) que interceptam as ações da IA:

1. **Security Hook:** Bloqueia comandos destrutivos (ex: `DROP TABLE`, `rm -rf`, `curl | bash`).
2. **Audit Hook:** Registra em um arquivo JSONL (`logs/audit.jsonl`) todas as ferramentas usadas pela IA, incluindo timestamps e status de sucesso/erro.
3. **Cost Guard Hook:** Monitora o uso de tokens da Anthropic e interrompe a sessão se o orçamento (ex: `$5.00`) for atingido.

---

## 9. O Hub de Conhecimento (KBs e Skills)

### 9.1. Knowledge Bases (`kb/`)
Lidas pelo Supervisor para planejamento:
- `sql-patterns`, `spark-patterns`, `pipeline-design`
- `data-quality`, `governance`, `semantic-modeling`
- `fabric`, `databricks`

### 9.2. Skills (`skills/`)
Lidas pelos especialistas para execução de código:
- 26 módulos Databricks (SDP, DABs, Unity Catalog, etc.)
- 5 módulos Microsoft Fabric (Medallion, Direct Lake, RTI, etc.)

---

## 10. Conexões com a Nuvem (MCP Servers)

O projeto usa quatro servidores MCP principais:
- `databricks`: Mais de 50 ferramentas (executar SQL, rodar jobs, listar catálogos).
- `fabric`: Ferramentas oficiais Microsoft para Workspaces e Lakehouses.
- `fabric_community`: Ferramentas comunitárias para OneLake e Modelos Semânticos.
- `fabric_rti`: Ferramentas para KQL e Activator (Real-Time Intelligence).

---

## 11. Comandos Disponíveis (Slash Commands)

| Comando | Modo | Agente Responsável |
| --- | --- | --- |
| `/sql` | Express | `sql-expert` |
| `/spark` | Express | `spark-expert` |
| `/pipeline` | Express | `pipeline-architect` |
| `/fabric` | Express | `pipeline-architect` |
| `/quality` | Express | `data-quality-steward` |
| `/governance` | Express | `governance-auditor` |
| `/semantic` | Express | `semantic-modeler` |
| `/plan` | Full | `supervisor` |
| `/health` | Internal | `supervisor` |
| `/status` | Internal | `supervisor` |

---

## 12. Configuração e Credenciais

Crie um arquivo `.env` na raiz do projeto:

```env
ANTHROPIC_API_KEY=sk-ant-...
DATABRICKS_HOST=https://adb-...
DATABRICKS_TOKEN=dapi...
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
FABRIC_WORKSPACE_ID=...
```

---

## 13. Qualidade de Código e Testes

O projeto usa `pytest`, `ruff`, `mypy` e `bandit`. A cobertura mínima exigida é de 80%.

```bash
make test
```

Os testes verificam:
- Carregamento dinâmico dos agentes no registry.
- Validação dos comandos no parser.
- Bloqueios do security hook.

---

## 14. Deploy e CI/CD (Publicação Automática)

- **Databricks Asset Bundles (DABs):** Configurado em `databricks.yml` para deploy em Dev, Staging e Prod.
- **GitHub Actions:** Workflows de CI (linting e testes) e CD (deploy automático).

---

## 15. Como Começar a Usar

1. Clone o repositório.
2. Crie um ambiente virtual (`python -m venv .venv`).
3. Instale as dependências (`pip install -e .`).
4. Configure o `.env`.
5. Execute `python main.py`.
6. Digite `/health` para validar as conexões.

---

## 16. Conclusão

O **Data Agents v2.0** representa uma arquitetura corporativa madura. A separação entre KBs (regras) e Skills (manuais), aliada ao registry dinâmico de agentes, transforma o projeto de um simples script em uma **plataforma extensível**. 

A introdução dos agentes de Qualidade, Governança e Semântica cobre o ciclo de vida completo dos dados, provando que sistemas multi-agente podem atuar de forma segura, governada e escalável em ambientes corporativos críticos.
