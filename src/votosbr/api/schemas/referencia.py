"""Schemas de listas de referência e metadados."""

from datetime import date

from pydantic import BaseModel

from votosbr.api.schemas.comum import DataHoraUTC


class LegislaturaOut(BaseModel):
    numero: int
    data_inicio: date
    data_fim: date


class PartidoOut(BaseModel):
    slug: str
    sigla: str
    nome: str | None
    extinto_em: date | None
    sucessor: str | None


class TemaOut(BaseModel):
    slug: str
    nome: str


class ValorEnum(BaseModel):
    valor: str
    rotulo: str


class AtualizacaoFonte(BaseModel):
    job: str
    fonte: str
    ultima_execucao_sucesso: DataHoraUTC | None
    dados_ate: date | None
    dados_desde: date


class Saude(BaseModel):
    status: str
    banco: str
