# License

## data-agents-copilot

Este projeto é distribuído sob a **MIT License**.

```
MIT License

Copyright (c) 2024-2025 Data Agents Copilot Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Referência ao Projeto Original

Este projeto é um fork pessoal e propositalmente reduzido de:

**[data-agents](https://github.com/ThomazRossito/data-agents)** por [Thomaz Rossito](https://github.com/ThomazRossito) — MIT License.

### Diferenças deste fork

Adições:

- GitHub Copilot Chat API como LLM principal (Anthropic continua como dependência secundária — qa_reviewer usa Haiku, supervisor usa Sonnet)
- Naming Guard com auto-trigger em DDL
- Workflows extras WF-06 e WF-07 (no contexto local)
- QA Orchestrator com score 0–1
- Failover automático de modelo (Opus → Sonnet → Haiku) em `agents/base.py` com detecção de 529/overloaded

Recursos do upstream **não reproduzidos** neste fork (lista parcial):

- Catalog Intelligence, Migration Expert, Semantic Modeler, Business Analyst, Business Monitor
- Genie Health Check, dashboard de monitoramento de 9 páginas
- 13+ MCP servers adicionais (Genie, Fabric SQL, RTI, Tavily, Firecrawl, GitHub, Postgres, etc.)

---

## Dependências de Terceiros

Este projeto depende de várias bibliotecas open-source sob suas respectivas licenças:

- **OpenAI Python SDK** — MIT License
- **Anthropic Python SDK** — MIT License
- **MCP Python SDK** — MIT License
- **Pydantic / pydantic-settings** — MIT License
- **Databricks SDK** — Apache 2.0
- **azure-identity** — MIT License
- **Chainlit** — Apache 2.0
- **Questionary** — MIT License
- **Rich** — MIT License
- **Python-dotenv** — BSD 3-Clause
- **PyYAML** — MIT License

Para lista completa, consulte `pyproject.toml` e `pip freeze`.

---

## Contribuições

Ao contribuir para este projeto, você concorda que suas contribuições serão licenciadas sob a mesma MIT License.

Veja [CONTRIBUTING.md](./CONTRIBUTING.md) para detalhes.

---

Dúvidas sobre licença? Abra uma [Discussion](https://github.com/arthurfr23/data-agents-copilot/discussions) no GitHub.
