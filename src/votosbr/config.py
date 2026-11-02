"""Configuração via variáveis de ambiente (seção 9)."""

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROJETO = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://votosbr:votosbr@localhost:5432/votosbr"
    # API usa um usuário somente leitura; sem valor, cai no DATABASE_URL (apenas em dev).
    database_url_readonly: str | None = None

    raw_store_path: Path = Path("data/raw")

    http_user_agent: str = "VotosBR/0.1 (+contato@exemplo.org)"
    http_timeout_s: float = 30.0
    http_max_rps_camara: float = 2.0
    http_max_rps_senado: float = 1.0
    http_max_tentativas: int = Field(default=5, ge=1)
    http_backoff_inicial_s: float = 1.0
    http_backoff_maximo_s: float = 60.0

    documento_hmac_secret: SecretStr | None = None
    metrica_n_minimo: int = 10

    ingestao_data_inicial: date = date(2026, 11, 1)
    janela_revisao_dias: int = Field(default=7, ge=0)
    tamanho_fatia_dias: int = Field(default=7, ge=1)

    api_cors_origins: list[str] = ["http://localhost:5173"]
    log_json: bool = True
    log_nivel: str = "INFO"

    # Diretórios de YAML versionados (seções 5.4 e 6.6)
    dir_seeds: Path = RAIZ_PROJETO / "seeds"
    dir_normalizacao: Path = RAIZ_PROJETO / "normalizacao"
    dir_curadoria: Path = RAIZ_PROJETO / "curadoria"

    @property
    def database_url_api(self) -> str:
        return self.database_url_readonly or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
