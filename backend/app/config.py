"""Configuração por variáveis de ambiente (nunca coloque segredos no código)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DentFlow"
    database_url: str = "sqlite:///./odonto.db"
    # Obrigatória em produção. Em desenvolvimento, sem ela o servidor recusa subir (ver main.py).
    secret_key: str = ""
    token_minutes: int = 12 * 60
    # Endereço(s) do frontend, separados por vírgula, para o CORS.
    frontend_url: str = "http://localhost:5173"
    ambiente: str = "dev"  # dev | prod
    # Pasta dos anexos (raio-X, fotos). Fora da pasta pública; só a API lê.
    pasta_anexos: str = "./anexos"
    anexo_max_mb: int = 10
    # IA (Claude). Sem a chave, as funções de IA respondem 503 e o resto do sistema segue normal.
    anthropic_api_key: str = ""
    ia_modelo: str = "claude-sonnet-5-5"        # resumo, chat, leitura de anexos, secretária
    ia_modelo_rapido: str = "claude-haiku-5-5"  # triagem

    @property
    def origens(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_url.split(",") if o.strip()]


@lru_cache
def settings() -> Settings:
    return Settings()
