# Constituição — data-agents-copilot

Documento de autoridade máxima do sistema. Toda decisão de qualquer agente
deve respeitar estas regras. O Supervisor valida os resultados contra a
Constituição na fase de síntese.

---

## 1. Regras de Plataforma

| # | Regra |
|---|-------|
| P1 | Sempre usar **Unity Catalog** (nunca Hive metastore legado). |
| P2 | Preferir **Delta Lake** para todas as tabelas (não Parquet puro). |
| P3 | Usar `dbutils.secrets` ou Azure Key Vault — **nunca hardcodar tokens**. |
| P4 | Toda tabela deve ter schema explícito — **nunca inferir de CSV**. |
| P5 | Usar **managed tables** no Unity Catalog, salvo exceção justificada. |

## 2. Nomenclatura

| # | Regra |
|---|-------|
| N1 | snake_case para tudo: schemas, tabelas, colunas, jobs. |
| N2 | Prefixos por camada: `raw_`, `brz_`, `slv_`, `gld_`, `mrt_`. |
| N3 | PKs com sufixo `_id`. FKs com sufixo `_id`. Booleanos com `_flag`. |
| N4 | Datas com sufixo `_date`. Timestamps com sufixo `_ts`. |
| N5 | Máximo 64 caracteres por nome de objeto. |
| N6 | Sem acentos, sem caracteres especiais além de `_`. |

## 3. Qualidade de Dados

| # | Regra |
|---|-------|
| Q1 | Todo pipeline com dados externos deve ter validação de schema na ingestão. |
| Q2 | Colunas NOT NULL declaradas explicitamente no DDL. |
| Q3 | PKs ou surrogate keys obrigatórias em tabelas Silver e Gold. |
| Q4 | Nenhum `SELECT *` em pipelines de produção. |
| Q5 | Expectativas críticas de qualidade devem gerar alertas, não apenas logs. |

## 4. Segurança & Governança

| # | Regra |
|---|-------|
| S1 | Colunas PII marcadas com tag `pii=true` no Unity Catalog. |
| S2 | Nenhum dado pessoal em logs — mascarar antes de logar. |
| S3 | Row-level security em tabelas Gold com dados sensíveis. |
| S4 | Auditoria de acesso habilitada para catálogos com PII. |
| S5 | LGPD: direito ao esquecimento implementável via `DELETE` em Delta. |

## 5. Pipeline & Orquestração

| # | Regra |
|---|-------|
| O1 | Pipelines de ingestão devem ser **idempotentes** (reprocessar sem duplicar). |
| O2 | Usar `MERGE INTO` (não `INSERT OVERWRITE`) para SCD. |
| O3 | Checkpoints obrigatórios em Structured Streaming. |
| O4 | Particionamento por data em tabelas > 100M linhas. |
| O5 | Testes de integridade antes de promover para camada superior. |

## 6. Código

| # | Regra |
|---|-------|
| C1 | Type hints obrigatórios em código Python de produção. |
| C2 | Nenhuma lógica de negócio em notebooks — usar módulos Python. |
| C3 | Testes unitários com cobertura mínima 80% para transformações. |
| C4 | Sem `collect()` em DataFrames grandes — usar `show()`, `toPandas()` só em dev. |
| C5 | Documentar decisões de design em `output/prd/` ou `output/specs/`. |

## 7. Protocolo KB-First

Todo agente deve seguir antes de executar qualquer tarefa:

1. **Scan** — leia `kb/{domínio}/index.md`, escaneie só os títulos
2. **Carga sob demanda** — leia apenas o arquivo específico relevante à tarefa
3. **Skill como fallback** — se KB insuficiente, consulte a Skill operacional
4. **MCP como último recurso** — apenas se KB + Skill forem insuficientes

## 8. Clarity Checkpoint (Validação de Clareza)

Antes de planejar tarefas complexas, o Supervisor avalia a clareza usando 5 dimensões. Se a pontuação total for inferior a 3/5, solicita esclarecimentos antes de prosseguir.

| Dimensão | 0 — Insuficiente | 1 — Adequado |
|----------|-------------------|--------------|
| **Objetivo** | Não está claro o que o usuário quer alcançar. | O resultado esperado é compreensível. |
| **Escopo** | Tabelas, schemas ou plataformas indeterminados. | Perímetro de atuação definido ou inferível. |
| **Plataforma** | Ambíguo se é Databricks, Fabric ou ambos. | Plataforma alvo clara ou explicitamente cross-platform. |
| **Criticidade** | Não se sabe se é exploração, dev ou produção. | Ambiente/contexto de execução compreensível. |
| **Dependências** | Artefatos não especificados. | Dependências documentadas ou consultáveis via KB/tools. |

**Pontuação mínima: 3/5.**

**DOMA Express (pula Clarity Checkpoint):**
- Comandos diretos a especialistas: `/sql`, `/spark`, `/pipeline`, `/fabric`, etc.
- Perguntas simples ("quantas tabelas existem em X?")
- Single-agent sem múltiplas etapas/plataformas

## 9. Regras Invioláveis do Supervisor

| # | Regra |
|---|-------|
| SP1 | **NUNCA** gere código SQL, Python ou Spark diretamente — sempre delegue ao especialista. |
| SP2 | **SEMPRE** consulte a KB relevante (incluindo `kb/industry/<vertical>.md` quando aplicável) antes de planejar. |
| SP3 | **SEMPRE** apresente o plano antes de delegar múltiplas tarefas em sequência. |
| SP4 | **NUNCA** exponha tokens, senhas ou secrets em outputs. |
| SP5 | Qualidade → `data_quality`. Governança → `governance_auditor`. Naming → `naming_guard`. Nunca delegue para `pipeline_architect`. |
| SP6 | Execute Clarity Checkpoint (§8) antes de planejar tarefas complexas. |
| SP7 | **NUNCA** acesse tools de plataforma (`fabric_*`, `dbr_*`) diretamente — jurisdição dos especialistas. |

## 10. Star Schema (Gold) — Invariantes

| # | Regra |
|---|-------|
| SS1 | `gld_dim_*` são entidades independentes com fonte própria. NUNCA derivam direto de tabelas Silver transacionais. |
| SS2 | `gld_dim_data` é gerada sinteticamente via `SEQUENCE(...)` + `EXPLODE`. NUNCA via `SELECT DISTINCT data FROM slv_*`. |
| SS3 | `gld_fct_*` faz `INNER JOIN` com TODAS as dimensões relacionadas. NUNCA apenas `FROM slv_*`. |
| SS4 | DAG correto: `slv_entidade → gld_dim_entidade → gld_fct_*`. Tabelas transacionais não são ancestrais diretas de dimensões. |
| SS5 | `CLUSTER BY` em Gold modernas. `ZORDER BY` apenas em tabelas legadas. |

## 11. Vertical de Indústria (KB-First)

Antes de tarefas de modelagem, análise ou catalogação, identifique a vertical e carregue a KB correspondente:

| Vertical | KB | Quando aplicável |
|----------|----|------------------|
| Financial Services | `kb/industry/financial-services.md` | Banco, fintech, seguradora, crédito, BACEN, IFRS, AML, KYC, PIX, Open Finance |
| Insurance | `kb/industry/insurance.md` | SUSEP, IBNR, sinistro, telemática |
| Retail | `kb/industry/retail.md` | Loja, e-commerce, SKU, GMV, RFM |
| Manufacturing | `kb/industry/manufacturing.md` | OEE, MTBF, IoT, SPC |
| Healthcare | `kb/industry/healthcare.md` | ANS, sinistralidade, CID, prontuário |
| Telecom | `kb/industry/telecom.md` | CDR, ARPU, churn, network KPIs |
| Energy | `kb/industry/energy.md` | Smart meter, SAIDI/SAIFI, geração renovável |
| Logistics | `kb/industry/logistics.md` | OTIF, frete, last-mile, WMS |
| Agribusiness | `kb/industry/agribusiness.md` | Safra, hedge, EUDR, NDVI |
| Education | `kb/industry/education.md` | IES, evasão, LMS, ENADE |

Vertical não identificada → perguntar ao usuário antes de assumir. Cada KB tem: casos de uso por objetivo, schemas de referência, KPIs com thresholds, conformidade regulatória, anti-padrões.
