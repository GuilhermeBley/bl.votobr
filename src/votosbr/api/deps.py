"""Dependências da API: sessão de banco somente leitura e configuração."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from votosbr.config import Settings, get_settings
from votosbr.db.session import engine_leitura, fabrica_sessao


def get_sessao() -> Iterator[Session]:
    with fabrica_sessao(engine_leitura())() as sessao:
        yield sessao


SessaoDep = Annotated[Session, Depends(get_sessao)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

PaginaDep = Annotated[int, Query(ge=1, description="Página, a partir de 1.")]
PorPaginaDep = Annotated[int, Query(ge=1, le=100, description="Itens por página (máx. 100).")]
