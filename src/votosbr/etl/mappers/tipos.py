"""Estruturas intermediárias staging -> core, independentes de fonte e de ORM."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from votosbr.domain.enums import (
    BancadaTipo,
    Casa,
    FonteDado,
    OrientacaoTipo,
    VotacaoModalidade,
    VotacaoObjeto,
    VotoTipo,
)


@dataclass(frozen=True)
class ProposicaoCore:
    casa: Casa
    fonte: FonteDado
    id_externo: str
    sigla_tipo: str
    numero: int
    ano: int
    ementa: str | None
    data_apresentacao: date | None
    url_fonte: str | None


@dataclass(frozen=True)
class VotacaoCore:
    id_publico: str
    casa: Casa
    fonte: FonteDado
    id_externo: str
    orgao_sigla: str
    data: date
    data_hora: datetime | None
    descricao: str | None
    modalidade: VotacaoModalidade
    objeto: VotacaoObjeto
    turno: int | None
    aprovado: bool | None
    resultado_fonte: str | None
    placar_fonte: dict[str, Any] | None
    url_fonte: str | None


@dataclass(frozen=True)
class VotoCore:
    id_externo_pessoa: str
    voto: VotoTipo
    voto_original: str
    mapeado: bool
    partido_sigla_fonte: str | None
    uf: str | None
    registrado_em: datetime | None


@dataclass(frozen=True)
class OrientacaoCore:
    bancada_sigla: str
    bancada_tipo: BancadaTipo
    orientacao: OrientacaoTipo
    orientacao_original: str
    mapeado: bool


@dataclass(frozen=True)
class PessoaCore:
    slug_base: str
    nome_civil: str
    nome_parlamentar: str
    nome_busca: str
    data_nascimento: date | None
    sexo: str | None
    uf_nascimento: str | None
    municipio_nascimento: str | None
    url_foto: str | None


@dataclass(frozen=True)
class NaoMapeado:
    campo: str
    valor: str
    exemplo_ref: str


@dataclass(frozen=True)
class VotacaoMapeada:
    votacao: VotacaoCore
    votos: list[VotoCore]
    orientacoes: list[OrientacaoCore]
    proposicoes: list[tuple[ProposicaoCore, str]]  # (proposição, papel OBJETO|AFETADA)
    nao_mapeados: list[NaoMapeado] = field(default_factory=list)
