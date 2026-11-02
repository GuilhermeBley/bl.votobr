"""Base declarativa, convenções de nomes e tipos compartilhados (seção 5.2)."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, Identity, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from votosbr.domain.enums import (
    BancadaTipo,
    Casa,
    FonteDado,
    OrientacaoTipo,
    VotacaoModalidade,
    VotacaoObjeto,
    VotoTipo,
)

CONVENCAO_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCAO_NOMES)


def _pg_enum(enum: type[StrEnum], nome: str) -> Enum:
    return Enum(enum, name=nome, values_callable=lambda membros: [m.value for m in membros])


# Instâncias únicas: cada tipo é criado uma vez no PostgreSQL.
CASA = _pg_enum(Casa, "casa")
FONTE_DADO = _pg_enum(FonteDado, "fonte_dado")
VOTO_TIPO = _pg_enum(VotoTipo, "voto_tipo")
ORIENTACAO_TIPO = _pg_enum(OrientacaoTipo, "orientacao_tipo")
VOTACAO_MODALIDADE = _pg_enum(VotacaoModalidade, "votacao_modalidade")
VOTACAO_OBJETO = _pg_enum(VotacaoObjeto, "votacao_objeto")
BANCADA_TIPO = _pg_enum(BancadaTipo, "bancada_tipo")


def pk_identity() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(always=True), primary_key=True)


class ComTimestamps:
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
