"""Engines e fábricas de sessão: escrita (ingestão) e somente leitura (API)."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from votosbr.config import get_settings


@lru_cache
def engine_escrita() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def engine_leitura() -> Engine:
    return create_engine(get_settings().database_url_api, pool_pre_ping=True)


def fabrica_sessao(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def sessao_escrita() -> Iterator[Session]:
    with fabrica_sessao(engine_escrita())() as sessao:
        yield sessao
