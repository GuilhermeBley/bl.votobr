"""Controle de ingestão: execuções, documentos brutos, pendências, checks e checkpoints."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from votosbr.db.base import FONTE_DADO, Base, pk_identity
from votosbr.domain.enums import FonteDado


class ExecucaoIngestao(Base):
    __tablename__ = "execucao_ingestao"

    id: Mapped[int] = pk_identity()
    job: Mapped[str] = mapped_column(Text)
    parametros: Mapped[dict[str, Any]] = mapped_column(JSONB)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text)  # EXECUTANDO | SUCESSO | SUCESSO_COM_ALERTAS | FALHA
    registros_lidos: Mapped[int | None] = mapped_column(Integer, server_default="0")
    registros_gravados: Mapped[int | None] = mapped_column(Integer, server_default="0")
    erros: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)


class RawDocumento(Base):
    """Metadados de cada resposta bruta; o corpo fica no RawStore (disco/S3)."""

    __tablename__ = "raw_documento"

    id: Mapped[int] = pk_identity()
    fonte: Mapped[FonteDado] = mapped_column(FONTE_DADO)
    url: Mapped[str] = mapped_column(Text)
    parametros: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    http_status: Mapped[int] = mapped_column(SmallInteger)
    conteudo_hash: Mapped[str] = mapped_column(Text)
    caminho_storage: Mapped[str] = mapped_column(Text)
    coletado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    execucao_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("execucao_ingestao.id"))


class ValorNaoMapeado(Base):
    __tablename__ = "valor_nao_mapeado"

    fonte: Mapped[FonteDado] = mapped_column(FONTE_DADO, primary_key=True)
    campo: Mapped[str] = mapped_column(Text, primary_key=True)
    valor: Mapped[str] = mapped_column(Text, primary_key=True)
    ocorrencias: Mapped[int] = mapped_column(Integer, server_default="1")
    primeira_ocorrencia: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ultima_ocorrencia: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    exemplo_ref: Mapped[str | None] = mapped_column(Text)


class ResultadoCheck(Base):
    __tablename__ = "resultado_check"

    execucao_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("execucao_ingestao.id"), primary_key=True
    )
    check_id: Mapped[str] = mapped_column(Text, primary_key=True)
    severidade: Mapped[str] = mapped_column(Text)  # ALERTA | ERRO
    quantidade: Mapped[int] = mapped_column(Integer)
    amostra: Mapped[Any | None] = mapped_column(JSONB)


class CheckpointIngestao(Base):
    """Progresso dos jobs incrementais por data (seção 6.2.1)."""

    __tablename__ = "checkpoint_ingestao"

    job: Mapped[str] = mapped_column(Text, primary_key=True)
    processado_ate: Mapped[date] = mapped_column(Date)
    execucao_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("execucao_ingestao.id"))
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
