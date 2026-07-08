from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Single shared admin password gating all write/chat endpoints.
    admin_password: str = "changeme"
    # Secret used to sign the admin session token.
    session_secret: str = "dev-secret-change-me"

    # LLM layer. Provider is swappable; "openai" is the default.
    # If the key is missing, the app falls back to a stub provider so it still boots.
    llm_provider: str = "openai"
    llm_model: str = "gpt-5.5"
    llm_endpoint: str = "responses"  # "responses" or "chat"
    openai_api_key: str = ""
    openai_base_url: str = ""
    anthropic_api_key: str = ""

    database_url: str = "sqlite:///./syllabus.db"

    # Frontend origin(s) allowed by CORS (comma-separated in env).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
