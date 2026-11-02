"""Temas, aliases de slug e registros de curadoria."""

from datetime import datetime
from typing import Any

from sqlalchemy import REAL, BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from votosbr.db.base import Base, pk_identity


class Tema(Base):
    __tablename__ = "tema"

    id: Mapped[int] = pk_identity()
    slug: Mapped[str] = mapped_column(Text, unique=True)
    nome: Mapped[str] = mapped_column(Text)


class ProcessoTema(Base):
    __tablename__ = "processo_tema"

    processo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("processo_legislativo.id"), primary_key=True
    )
    tema_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tema.id"), primary_key=True)
    origem: Mapped[str] = mapped_column(Text)  # CURADORIA | PALAVRA_CHAVE_FONTE


class SlugAlias(Base):
    __tablename__ = "slug_alias"

    entidade: Mapped[str] = mapped_column(Text, primary_key=True)  # pessoa|processo|norma|partido
    slug_antigo: Mapped[str] = mapped_column(Text, primary_key=True)
    entidade_id: Mapped[int] = mapped_column(BigInteger)


class CuradoriaLog(Base):
    __tablename__ = "curadoria_log"

    id: Mapped[int] = pk_identity()
    entidade: Mapped[str] = mapped_column(Text)
    entidade_id: Mapped[int] = mapped_column(BigInteger)
    campo: Mapped[str] = mapped_column(Text)
    valor_anterior: Mapped[Any | None] = mapped_column(JSONB)
    valor_novo: Mapped[Any | None] = mapped_column(JSONB)
    autor: Mapped[str] = mapped_column(Text)
    motivo: Mapped[str | None] = mapped_column(Text)
    em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PessoaMatchCandidato(Base):
    """Fila de revisão manual de possíveis pessoas duplicadas (seção 6.6)."""

    __tablename__ = "pessoa_match_candidato"

    pessoa_a_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pessoa.id"), primary_key=True)
    pessoa_b_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pessoa.id"), primary_key=True)
    score: Mapped[float] = mapped_column(REAL)
    motivo: Mapped[str] = mapped_column(Text)
    decisao: Mapped[str | None] = mapped_column(Text)  # MESMA_PESSOA | DIFERENTES | null
