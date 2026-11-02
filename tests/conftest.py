import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from votosbr.config import RAIZ_PROJETO
from votosbr.db.base import Base
from votosbr.domain.classificacao import ClassificadorObjeto
from votosbr.domain.normalizacao import Normalizador

FIXTURES = Path(__file__).parent / "fixtures"

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://votosbr:votosbr@localhost:5432/votosbr_test"
)


def carregar_fixture(caminho: str) -> Any:
    return json.loads((FIXTURES / caminho).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def normalizador() -> Normalizador:
    return Normalizador.carregar(RAIZ_PROJETO / "normalizacao")


@pytest.fixture(scope="session")
def classificador() -> ClassificadorObjeto:
    return ClassificadorObjeto.de_yaml(RAIZ_PROJETO / "normalizacao" / "objeto_votacao.yaml")


def _criar_banco_se_preciso(url: str) -> None:
    alvo = make_url(url)
    admin = create_engine(alvo.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        existe = c.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": alvo.database}
        )
        if not existe:
            c.execute(text(f'CREATE DATABASE "{alvo.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine_teste() -> Iterator[Engine]:
    """Banco de teste migrado do zero com Alembic. Pula se não houver Postgres disponível."""
    try:
        _criar_banco_se_preciso(TEST_DATABASE_URL)
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL indisponível em TEST_DATABASE_URL: {exc.orig}")
    cfg = Config(str(RAIZ_PROJETO / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_PROJETO / "src/votosbr/db/migrations"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def fabrica(engine_teste: Engine) -> sessionmaker[Session]:
    """Banco limpo a cada teste."""
    tabelas = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine_teste.begin() as c:
        c.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))
    return sessionmaker(engine_teste, expire_on_commit=False)
