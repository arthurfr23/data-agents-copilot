"""Testes para scripts/bootstrap.py — apenas funções puras (sem I/O interativo)."""

from __future__ import annotations

import scripts.bootstrap as bootstrap


class TestRenderEnv:
    """_render_env gera o conteúdo do .env a partir das seções coletadas."""

    def test_empty_sections_produces_only_system_defaults(self):
        content = bootstrap._render_env(
            {"Anthropic / Claude": {}, "Databricks": {}, "Microsoft Fabric": {}}
        )
        assert "DEFAULT_MODEL=claude-sonnet-4-6" in content
        assert "MAX_BUDGET_USD=1.0" in content
        assert "MEMORY_ENABLED=true" in content
        # Nenhuma seção customizada foi renderizada
        assert "ANTHROPIC_API_KEY" not in content
        assert "DATABRICKS_HOST" not in content

    def test_anthropic_only_renders_just_api_key(self):
        content = bootstrap._render_env(
            {
                "Anthropic / Claude": {
                    "ANTHROPIC_API_KEY": "sk-ant-test",
                    "ANTHROPIC_BASE_URL": "",
                },
                "Databricks": {},
                "Microsoft Fabric": {},
            }
        )
        assert "ANTHROPIC_API_KEY=sk-ant-test" in content
        # Valor vazio é omitido
        assert "ANTHROPIC_BASE_URL=" not in content

    def test_full_databricks_section(self):
        content = bootstrap._render_env(
            {
                "Anthropic / Claude": {"ANTHROPIC_API_KEY": "sk-ant-x"},
                "Databricks": {
                    "DATABRICKS_HOST": "https://adb.test",
                    "DATABRICKS_TOKEN": "dapi123",
                    "DATABRICKS_SQL_WAREHOUSE_ID": "abc",
                },
                "Microsoft Fabric": {},
            }
        )
        assert "DATABRICKS_HOST=https://adb.test" in content
        assert "DATABRICKS_TOKEN=dapi123" in content
        assert "DATABRICKS_SQL_WAREHOUSE_ID=abc" in content

    def test_sections_with_only_empty_values_are_skipped(self):
        content = bootstrap._render_env(
            {
                "Anthropic / Claude": {"ANTHROPIC_API_KEY": "sk-ant-x"},
                "Databricks": {
                    "DATABRICKS_HOST": "",
                    "DATABRICKS_TOKEN": "",
                },
                "Microsoft Fabric": {},
            }
        )
        # Header da seção Databricks não aparece se tudo está vazio
        assert "─── Databricks ───" not in content
        assert "ANTHROPIC_API_KEY=sk-ant-x" in content

    def test_output_ends_with_newline(self):
        content = bootstrap._render_env({"Anthropic / Claude": {}})
        assert content.endswith("\n")


class TestValidateAnthropicKey:
    """_validate_anthropic_key aceita sk-ant- e outros formatos (proxy)."""

    def test_accepts_anthropic_native_key(self):
        assert bootstrap._validate_anthropic_key("sk-ant-abc123") is True

    def test_accepts_custom_proxy_key(self, capsys):
        # Proxy keys (Bedrock/Azure) não começam com sk-ant-; são aceitas
        # com uma mensagem informativa, mas ainda retornam True.
        assert bootstrap._validate_anthropic_key("custom-proxy-key") is True
        captured = capsys.readouterr()
        assert "proxy" in captured.out.lower()

    def test_rejects_empty_string(self):
        assert bootstrap._validate_anthropic_key("") is False
