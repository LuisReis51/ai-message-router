from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- OpenAI (ChatGPT) ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # --- Anthropic (Claude) ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # --- Google (Gemini) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # --- xAI (Grok) ---
    grok_api_key: str = ""
    grok_model: str = "grok-3"
    grok_base_url: str = "https://api.x.ai/v1"

    # --- DeepSeek ---
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Windsurf ---
    windsurf_host: str = "localhost"
    windsurf_port: int = 3000

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    # --- Router ---
    provider_timeout: int = Field(default=60, description="Timeout per provider in seconds")
    max_concurrency: int = Field(default=6, description="Max simultaneous provider calls")


settings = Settings()
