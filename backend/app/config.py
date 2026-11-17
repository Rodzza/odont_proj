"""Configuração por variáveis de ambiente (nunca coloque segredos no código)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "OdontoNotes"
    database_url: str = "sqlite:///./odonto.db"
    # Obrigatória em produção. Em desenvolvimento, sem ela o servidor recusa subir (ver main.py).
    secret_key: str = ""
    token_minutes: int = 12 * 60
    # Endereço(s) do frontend, separados por vírgula, para o CORS.
    frontend_url: str = "http://localhost:5173"
    ambiente: str = "dev"  # dev | prod

    @property
    def origens(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_url.split(",") if o.strip()]


@lru_cache
def settings() -> Settings:
    return Settings()
