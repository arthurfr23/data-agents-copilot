import json
from functools import cached_property

from openai import OpenAI
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── GitHub Copilot ──────────────────────────────────────────────────────
    github_token: str = Field(..., alias="GITHUB_TOKEN")
    default_model: str = Field("claude-sonnet-4-5", alias="DEFAULT_MODEL")
    tier_model_map: dict = Field(
        default={"T1": "claude-sonnet-4-5", "T2": "gpt-4o", "T3": "gpt-4o-mini"},
        alias="TIER_MODEL_MAP",
    )
    tier_turns_map: dict = Field(
        default={"T1": 20, "T2": 12, "T3": 5},
        alias="TIER_TURNS_MAP",
    )

    # ── Databricks ──────────────────────────────────────────────────────────
    databricks_host: str = Field("", alias="DATABRICKS_HOST")
    databricks_token: str = Field("", alias="DATABRICKS_TOKEN")
    databricks_sql_warehouse_id: str = Field("", alias="DATABRICKS_SQL_WAREHOUSE_ID")
    databricks_catalog: str = Field("main", alias="DATABRICKS_CATALOG")
    databricks_schema: str = Field("default", alias="DATABRICKS_SCHEMA")

    # ── Microsoft Fabric ────────────────────────────────────────────────────
    azure_tenant_id: str = Field("", alias="AZURE_TENANT_ID")
    azure_client_id: str = Field("", alias="AZURE_CLIENT_ID")
    azure_client_secret: str = Field("", alias="AZURE_CLIENT_SECRET")
    fabric_workspace_id: str = Field("", alias="FABRIC_WORKSPACE_ID")

    # ── Controles ───────────────────────────────────────────────────────────
    max_turns: int = Field(50, alias="MAX_TURNS")
    max_budget_tokens: int = Field(500_000, alias="MAX_BUDGET_TOKENS")
    agent_permission_mode: str = Field("bypassPermissions", alias="AGENT_PERMISSION_MODE")
    console_log_level: str = Field("WARNING", alias="CONSOLE_LOG_LEVEL")
    memory_enabled: bool = Field(True, alias="MEMORY_ENABLED")

    @field_validator("tier_model_map", "tier_turns_map", mode="before")
    @classmethod
    def parse_json_field(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @cached_property
    def copilot_client(self) -> OpenAI:
        return OpenAI(
            base_url="https://api.githubcopilot.com",
            api_key=self.github_token,
            default_headers={
                "Copilot-Integration-Id": "vscode-chat",
                "Editor-Version": "vscode/1.90.0",
            },
        )

    def model_for_tier(self, tier: str) -> str:
        return self.tier_model_map.get(tier, self.default_model)

    def turns_for_tier(self, tier: str) -> int:
        return self.tier_turns_map.get(tier, 10)

    def has_databricks(self) -> bool:
        return bool(self.databricks_host and self.databricks_token)

    def has_fabric(self) -> bool:
        return bool(self.azure_tenant_id and self.azure_client_id and self.fabric_workspace_id)

    def diagnostics(self) -> dict:
        return {
            "copilot": bool(self.github_token),
            "databricks": self.has_databricks(),
            "fabric": self.has_fabric(),
        }


settings = Settings()
