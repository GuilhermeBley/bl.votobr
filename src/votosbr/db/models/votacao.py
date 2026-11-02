"""Votações, votos e orientações."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from votosbr.db.base import (
    CASA,
    FONTE_DADO,
    ORIENTACAO_TIPO,
    VOTACAO_MODALIDADE,
    VOTACAO_OBJETO,
    VOTO_TIPO,
    Base,
    ComTimestamps,
    pk_identity,
)
from votosbr.domain.enums import (
    Casa,
    FonteDado,
    OrientacaoTipo,
    VotacaoModalidade,
    VotacaoObjeto,
    VotoTipo,
)


class Votacao(ComTimestamps, Base):
    __tablename__ = "votacao"
    __table_args__ = (
        UniqueConstraint("fonte", "id_externo"),
        Index("votacao_data", "casa", text("data DESC")),
    )

    id: Mapped[int] = pk_identity()
    id_publico: Mapped[str] = mapped_column(Text, unique=True)  # 'camara-2265603-43'
    casa: Mapped[Casa] = mapped_column(CASA)
    fonte: Mapped[FonteDado] = mapped_column(FONTE_DADO)
    id_externo: Mapped[str] = mapped_column(Text)
    orgao_sigla: Mapped[str] = mapped_column(Text)
    data: Mapped[date] = mapped_column(Date)
    data_hora: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    descricao: Mapped[str | None] = mapped_column(Text)
    modalidade: Mapped[VotacaoModalidade] = mapped_column(
        VOTACAO_MODALIDADE, server_default=VotacaoModalidade.DESCONHECIDA.value
    )
    objeto: Mapped[VotacaoObjeto] = mapped_column(
        VOTACAO_OBJETO, server_default=VotacaoObjeto.OUTRO.value
    )
    turno: Mapped[int | None] = mapped_column(SmallInteger)
    principal: Mapped[bool] = mapped_column(Boolean, server_default="false")
    principal_origem: Mapped[str | None] = mapped_column(Text)  # HEURISTICA | CURADORIA
    aprovado: Mapped[bool | None] = mapped_column(Boolean)
    resultado_fonte: Mapped[str | None] = mapped_column(Text)
    placar_fonte: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    url_fonte: Mapped[str | None] = mapped_column(Text)
    raw_documento_id: Mapped[int | None] = mapped_column(BigInteger)
    removido_na_fonte_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VotacaoProposicao(Base):
    __tablename__ = "votacao_proposicao"

    votacao_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("votacao.id"), primary_key=True)
    proposicao_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("proposicao.id"), primary_key=True
    )
    papel: Mapped[str] = mapped_column(Text, primary_key=True)  # OBJETO | AFETADA


class Voto(Base):
    __tablename__ = "voto"
    __table_args__ = (
        Index("voto_pessoa", "pessoa_id", "votacao_id"),
        Index("voto_votacao_tipo", "votacao_id", "voto"),
    )

    votacao_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("votacao.id"), primary_key=True)
    pessoa_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pessoa.id"), primary_key=True)
    voto: Mapped[VotoTipo] = mapped_column(VOTO_TIPO)
    voto_original: Mapped[str] = mapped_column(Text)
    derivado: Mapped[bool] = mapped_column(Boolean, server_default="false")
    partido_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("partido.id"))
    partido_sigla_fonte: Mapped[str | None] = mapped_column(Text)
    uf: Mapped[str | None] = mapped_column(CHAR(2))
    registrado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Orientacao(Base):
    __tablename__ = "orientacao"

    votacao_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("votacao.id"), primary_key=True)
    bancada_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bancada.id"), primary_key=True)
    orientacao: Mapped[OrientacaoTipo] = mapped_column(ORIENTACAO_TIPO)
    orientacao_original: Mapped[str] = mapped_column(Text)
