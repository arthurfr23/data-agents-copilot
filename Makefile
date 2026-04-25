.PHONY: install lint format type-check security test run ui deploy-dev deploy-staging deploy-prod

install:
	pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check .

format:
	ruff format .

type-check:
	mypy agents/ config/ hooks/

security:
	bandit -r agents/ config/ hooks/ -ll

test:
	pytest tests/ -v --tb=short

run:
	python main.py

ui:
	chainlit run ui/chainlit_app.py --port 8503

deploy-dev:
	databricks bundle deploy --target dev

deploy-staging:
	databricks bundle deploy --target staging

deploy-prod:
	databricks bundle deploy --target prod

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete; \
	rm -rf .coverage htmlcov/ .mypy_cache/ .ruff_cache/
