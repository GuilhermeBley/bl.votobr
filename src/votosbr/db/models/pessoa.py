"""Pessoas, identificadores por fonte, mandatos, exercícios e filiações."""

from datetime import date

from sqlalchemy import (
    CHAR,
    BigInteger,
    Date,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from votosbr.db.base import CASA, FONTE_DADO, Base, ComTimestamps, pk_identity
from votosbr.domain.enums import Casa, FonteDado


class Pessoa(ComTimestamps, Base):
    __tablename__ = "pessoa"
    __table_args__ = (
        Index(
            "pessoa_nome_busca_trgm",
            "nome_busca",
            postgresql_using="gin",
            postgresql_ops={"nome_busca": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = pk_identity()
    slug: Mapped[str] = mapped_column(Text, unique=True)
    nome_civil: Mapped[str] = mapped_column(Text)
    nome_parlamentar: Mapped[str] = mapped_column(Text)
    nome_busca: Mapped[str] = mapped_column(Text)
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    sexo: Mapped[str | None] = mapped_column(CHAR(1))
    uf_nascimento: Mapped[str | None] = mapped_column(CHAR(2))
    municipio_nascimento: Mapped[str | None] = mapped_column(Text)
    url_foto: Mapped[str | None] = mapped_column(Text)
    # HMAC-SHA256(CPF, segredo), só para resolver identidade; nunca exposto. Preferir não preencher.
    documento_hmac: Mapped[str | None] = mapped_column(Text)


class IdentificadorExterno(Base):
    __tablename__ = "identificador_externo"

    pessoa_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pessoa.id"))
    fonte: Mapped[FonteDado] = mapped_column(FONTE_DADO, primary_key=True)
    id_externo: Mapped[str] = mapped_column(Text, primary_key=True)


class Mandato(Base):
    __tablename__ = "mandato"
    __table_args__ = (UniqueConstraint("pessoa_id", "casa", "legislatura_inicio", "uf"),)

    id: Mapped[int] = pk_identity()
    pessoa_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pessoa.id"))
    casa: Mapped[Casa] = mapped_column(CASA)
    uf: Mapped[str] = mapped_column(CHAR(2))
    legislatura_inicio: Mapped[int] = mapped_column(SmallInteger, ForeignKey("legislatura.numero"))
    legislatura_fim: Mapped[int] = mapped_column(SmallInteger, ForeignKey("legislatura.numero"))
    condicao: Mapped[str | None] = mapped_column(Text)  # TITULAR | SUPLENTE | EFETIVADO
    data_inicio: Mapped[date | None] = mapped_column(Date)
    data_fim: Mapped[date | None] = mapped_column(Date)
    fonte: Mapped[FonteDado] = mapped_column(FONTE_DADO)
    id_externo: Mapped[str | None] = mapped_column(Text)


class Exercicio(Base):
    __tablename__ = "exercicio"
    __table_args__ = (Index("exercicio_periodo", "mandato_id", "data_inicio", "data_fim"),)

    id: Mapped[int] = pk_identity()
    mandato_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("mandato.id"))
    data_inicio: Mapped[date] = mapped_column(Date)
    data_fim: Mapped[date | None] = mapped_column(Date)  # null = em curso
    situacao: Mapped[str] = mapped_column(Text)  # EXERCICIO | LICENCA | AFASTADO | ...
    motivo: Mapped[str | None] = mapped_column(Text)  # texto original da fonte


class Filiacao(Base):
    __tablename__ = "filiacao"

    pessoa_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pessoa.id"), primary_key=True)
    partido_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("partido.id"), primary_key=True)
    data_inicio: Mapped[date] = mapped_column(Date, primary_key=True)
    data_fim: Mapped[date | None] = mapped_column(Date)
    fonte: Mapped[FonteDado] = mapped_column(FONTE_DADO)
