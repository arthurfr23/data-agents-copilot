# ═══════════════════════════════════════════════════════════════════
# Data Agents — Makefile
# Automação de tarefas comuns de desenvolvimento e deploy
# ═══════════════════════════════════════════════════════════════════

.PHONY: help install dev test lint format type-check security clean run deploy-staging deploy-prod

# Cores para output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

help: ## Exibe esta ajuda
	@echo ""
	@echo "$(CYAN)Data Agents — Comandos disponíveis:$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ─── Setup ────────────────────────────────────────────────────────

install: ## Instala dependências de produção
	pip install -e .

dev: ## Instala dependências de desenvolvimento
	pip install -e ".[dev]"

# ─── Quality ──────────────────────────────────────────────────────

test: ## Executa testes com cobertura
	pytest tests/ -v --tb=short \
		--cov=agents --cov=config --cov=hooks --cov=commands \
		--cov-report=term-missing \
		--cov-fail-under=60

lint: ## Executa linter (ruff check)
	ruff check . --output-format=full

format: ## Formata código (ruff format)
	ruff format .

type-check: ## Verifica tipos (mypy)
	mypy --ignore-missing-imports agents/ config/ hooks/ commands/

security: ## Scan de segurança (bandit)
	bandit -r agents/ config/ hooks/ commands/ -ll --skip B101

# ─── Execução ─────────────────────────────────────────────────────

run: ## Inicia o Data Agents em modo interativo
	python main.py

# ─── Deploy ───────────────────────────────────────────────────────

deploy-staging: ## Deploy para Databricks Staging
	databricks bundle deploy --target staging

deploy-prod: ## Deploy para Databricks Production
	databricks bundle deploy --target production

# ─── Limpeza ──────────────────────────────────────────────────────

clean: ## Remove arquivos temporários e cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov coverage.xml
	rm -rf dist build *.egg-info
	@echo "$(GREEN)Limpeza concluída.$(RESET)"
