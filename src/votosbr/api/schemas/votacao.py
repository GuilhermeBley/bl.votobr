"""Schemas de resposta de votações e votos (seção 7.3)."""

from datetime import date

from pydantic import BaseModel

from votosbr.api.schemas.comum import Aviso, DataHoraUTC, FonteOut
from votosbr.domain.enums import (
    BancadaTipo,
    Casa,
    OrientacaoTipo,
    VotacaoModalidade,
    VotacaoObjeto,
    VotoTipo,
)


class PartidoRef(BaseModel):
    slug: str | None
    sigla: str


class ParlamentarRef(BaseModel):
    slug: str
    nome: str
    url_foto: str | None


class ProcessoRef(BaseModel):
    slug: str
    titulo: str


class ProposicaoRef(BaseModel):
    casa: Casa
    sigla: str
    numero: int
    ano: int
    papel: str


class OrientacaoOut(BaseModel):
    bancada: str
    tipo: BancadaTipo
    orientacao: OrientacaoTipo
    orientacao_original: str


class PlacarPartido(BaseModel):
    partido: PartidoRef
    orientacao: OrientacaoTipo | None
    contagem: dict[VotoTipo, int]


class VotacaoResumoOut(BaseModel):
    id: str
    casa: Casa
    orgao: str
    data: date
    data_hora: DataHoraUTC | None
    descricao: str | None
    modalidade: VotacaoModalidade
    objeto: VotacaoObjeto
    turno: int | None
    principal: bool
    aprovado: bool | None


class VotacaoDetalheOut(VotacaoResumoOut):
    placar: dict[VotoTipo, int]
    placar_por_partido: list[PlacarPartido]
    orientacoes: list[OrientacaoOut]
    processo: ProcessoRef | None
    proposicoes: list[ProposicaoRef]
    avisos: list[Aviso]
    fontes: list[FonteOut]


class VotoOut(BaseModel):
    parlamentar: ParlamentarRef
    partido: PartidoRef | None
    uf: str | None
    voto: VotoTipo
    voto_original: str
    derivado: bool
    orientacao_partido: OrientacaoTipo | None
    seguiu_orientacao_partido: bool | None


class GrupoPlacar(BaseModel):
    grupo: str  # sigla do partido ou UF
    contagem: dict[VotoTipo, int]
