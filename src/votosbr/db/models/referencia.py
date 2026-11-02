"""Legislaturas, partidos e bancadas."""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, SmallInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from votosbr.db.base import BANCADA_TIPO, CASA, FONTE_DADO, Base, ComTimestamps, pk_identity
from votosbr.domain.enums import BancadaTipo, Casa, FonteDado


class Legislatura(Base):
    __tablename__ = "legislatura"

    numero: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    data_inicio: Mapped[date] = mapped_column(Date)
    data_fim: Mapped[date] = mapped_column(Date)


class Partido(ComTimestamps, Base):
    __tablename__ = "partido"

    id: Mapped[int] = pk_identity()
    slug: Mapped[str] = mapped_column(Text, unique=True)
    sigla_atual: Mapped[str] = mapped_column(Text)
    nome: Mapped[str | None] = mapped_column(Text)
    numero_eleitoral: Mapped[int | None] = mapped_column(SmallInteger)
    data_registro: Mapped[date | None] = mapped_column(Date)
    data_extincao: Mapped[date | None] = mapped_column(Date)
    sucessor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("partido.id"))


class PartidoAlias(Base):
    """Siglas históricas e variações por fonte. Renomeação = mesmo partido, novo alias."""

    __tablename__ = "partido_alias"
    __table_args__ = (UniqueConstraint("fonte", "sigla", "valido_de"),)

    id: Mapped[int] = pk_identity()
    partido_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("partido.id"))
    fonte: Mapped[FonteDado] = mapped_column(FONTE_DADO)
    sigla: Mapped[str] = mapped_column(Text)
    id_externo: Mapped[str | None] = mapped_column(Text)
    valido_de: Mapped[date | None] = mapped_column(Date)
    valido_ate: Mapped[date | None] = mapped_column(Date)


class Bancada(Base):
    __tablename__ = "bancada"
    __table_args__ = (UniqueConstraint("casa", "sigla"),)

    id: Mapped[int] = pk_identity()
    casa: Mapped[Casa] = mapped_column(CASA)
    # Sigla como vem na fonte: "PT", "Governo", "Fdr PT-PCdoB-PV"
    sigla: Mapped[str] = mapped_column(Text)
    tipo: Mapped[BancadaTipo] = mapped_column(BANCADA_TIPO)
    partido_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("partido.id"))
    nome: Mapped[str | None] = mapped_column(Text)


class BancadaMembro(Base):
    """Composição de blocos e federações (métricas de alinhamento; fase 3+)."""

    __tablename__ = "bancada_membro"

    bancada_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bancada.id"), primary_key=True)
    partido_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("partido.id"), primary_key=True)
    valido_de: Mapped[date] = mapped_column(Date, primary_key=True)
    valido_ate: Mapped[date | None] = mapped_column(Date)
