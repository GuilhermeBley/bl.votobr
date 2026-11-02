"""Normas, processos legislativos e proposições."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from votosbr.db.base import CASA, FONTE_DADO, Base, ComTimestamps, pk_identity
from votosbr.domain.enums import Casa, FonteDado


class Norma(Base):
    __tablename__ = "norma"
    __table_args__ = (
        UniqueConstraint("tipo", "numero", "ano"),
        Index("norma_busca", "busca", postgresql_using="gin"),
    )

    id: Mapped[int] = pk_identity()
    slug: Mapped[str] = mapped_column(Text, unique=True)  # 'lei-12965-2014'
    tipo: Mapped[str] = mapped_column(Text)
    numero: Mapped[int] = mapped_column(Integer)
    ano: Mapped[int] = mapped_column(SmallInteger)
    data_assinatura: Mapped[date | None] = mapped_column(Date)
    data_publicacao: Mapped[date | None] = mapped_column(Date)
    ementa: Mapped[str | None] = mapped_column(Text)
    apelido: Mapped[str | None] = mapped_column(Text)
    urn_lexml: Mapped[str | None] = mapped_column(Text, unique=True)
    url_texto: Mapped[str | None] = mapped_column(Text)
    busca: Mapped[str | None] = mapped_column(TSVECTOR)  # mantido por trigger (T-404)


class ProcessoLegislativo(ComTimestamps, Base):
    __tablename__ = "processo_legislativo"

    id: Mapped[int] = pk_identity()
    slug: Mapped[str] = mapped_column(Text, unique=True)
    titulo: Mapped[str] = mapped_column(Text)
    norma_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("norma.id"), unique=True)
    situacao: Mapped[str] = mapped_column(Text)
    destaque: Mapped[bool] = mapped_column(Boolean, server_default="false")
    busca: Mapped[str | None] = mapped_column(TSVECTOR)


class Proposicao(ComTimestamps, Base):
    __tablename__ = "proposicao"
    __table_args__ = (
        UniqueConstraint("fonte", "id_externo"),
        Index("proposicao_identificacao", "sigla_tipo", "numero", "ano"),
    )

    id: Mapped[int] = pk_identity()
    casa: Mapped[Casa] = mapped_column(CASA)
    fonte: Mapped[FonteDado] = mapped_column(FONTE_DADO)
    id_externo: Mapped[str] = mapped_column(Text)
    processo_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("processo_legislativo.id")
    )
    sigla_tipo: Mapped[str] = mapped_column(Text)
    numero: Mapped[int] = mapped_column(Integer)
    ano: Mapped[int] = mapped_column(SmallInteger)
    ementa: Mapped[str | None] = mapped_column(Text)
    ementa_detalhada: Mapped[str | None] = mapped_column(Text)
    palavras_chave: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    data_apresentacao: Mapped[date | None] = mapped_column(Date)
    situacao_fonte: Mapped[str | None] = mapped_column(Text)
    url_fonte: Mapped[str | None] = mapped_column(Text)
    url_inteiro_teor: Mapped[str | None] = mapped_column(Text)
    raw_documento_id: Mapped[int | None] = mapped_column(BigInteger)
    removido_na_fonte_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProposicaoRelacao(Base):
    __tablename__ = "proposicao_relacao"

    origem_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("proposicao.id"), primary_key=True
    )
    destino_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("proposicao.id"), primary_key=True
    )
    # MESMA_MATERIA_OUTRA_CASA | APENSADA_A | CONVERTIDA_EM | ACESSORIA_DE
    tipo: Mapped[str] = mapped_column(Text, primary_key=True)
    fonte: Mapped[FonteDado] = mapped_column(FONTE_DADO)
