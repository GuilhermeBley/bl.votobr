"""Schemas de staging da API v2 da Câmara (nomes originais da fonte).

Derivados de tests/fixtures/camara/ (coletados em 2026-11-01). Campos extras são aceitos sem
falhar; só declaramos o que o pipeline usa. Datas/horas vêm sem fuso (horário de Brasília).
"""

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ModeloCamara(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)


class Link(ModeloCamara):
    rel: str
    href: str


class Resposta(ModeloCamara, Generic[T]):
    dados: T
    links: list[Link] = []


class ProposicaoResumo(ModeloCamara):
    """Itens de `objetosPossiveis` e `proposicoesAfetadas` no detalhe da votação."""

    id: int
    uri: str
    siglaTipo: str
    codTipo: int | None = None
    numero: int
    ano: int  # pode vir 0 em objetos acessórios (pareceres, destaques)
    ementa: str | None = None
    dataApresentacao: datetime | None = None


class VotacaoResumo(ModeloCamara):
    """Item de `GET /votacoes`."""

    id: str  # ex.: "2635476-36"
    uri: str
    data: date
    dataHoraRegistro: datetime | None = None
    siglaOrgao: str
    uriOrgao: str | None = None
    uriEvento: str | None = None
    proposicaoObjeto: str | None = None  # ex.: "REQ 4194/2026"
    uriProposicaoObjeto: str | None = None
    descricao: str | None = None
    aprovacao: int | None = None  # 1 aprovada, 0 rejeitada


class EfeitoRegistrado(ModeloCamara):
    uriProposicao: str | None = None
    tituloProposicao: str | None = None
    descResultado: str | None = None
    dataHoraResultado: datetime | None = None


class VotacaoDetalhe(ModeloCamara):
    """`GET /votacoes/{id}`."""

    id: str
    uri: str
    data: date
    dataHoraRegistro: datetime | None = None
    siglaOrgao: str
    idOrgao: int | None = None
    uriEvento: str | None = None
    idEvento: int | None = None
    descricao: str | None = None
    aprovacao: int | None = None
    descUltimaAberturaVotacao: str | None = None
    dataHoraUltimaAberturaVotacao: datetime | None = None
    efeitosRegistrados: list[EfeitoRegistrado] = []
    objetosPossiveis: list[ProposicaoResumo] = []
    proposicoesAfetadas: list[ProposicaoResumo] = []


class DeputadoResumo(ModeloCamara):
    """`deputado_` dentro de um voto e itens de `GET /deputados`.

    A fonte também traz `email`; não é usado nem armazenado no core.
    """

    id: int
    uri: str
    nome: str
    siglaPartido: str | None = None
    uriPartido: str | None = None
    siglaUf: str | None = None
    idLegislatura: int | None = None
    urlFoto: str | None = None


class VotoCamara(ModeloCamara):
    """Item de `GET /votacoes/{id}/votos`. Só lista quem registrou voto (seção 2.2, item 3)."""

    tipoVoto: str
    dataRegistroVoto: datetime | None = None
    deputado_: DeputadoResumo


class OrientacaoCamara(ModeloCamara):
    """Item de `GET /votacoes/{id}/orientacoes`. `orientacaoVoto` vazio = não orientou."""

    orientacaoVoto: str
    codTipoLideranca: str  # "P" partido, "B" bloco/federação/Governo/Oposição/Maioria/Minoria
    siglaPartidoBloco: str
    codPartidoBloco: int | None = None
    uriPartidoBloco: str | None = None


class UltimoStatus(ModeloCamara):
    id: int
    nome: str
    siglaPartido: str | None = None
    siglaUf: str | None = None
    idLegislatura: int | None = None
    urlFoto: str | None = None
    data: date | None = None
    nomeEleitoral: str | None = None
    situacao: str | None = None
    condicaoEleitoral: str | None = None
    descricaoStatus: str | None = None


class DeputadoDetalhe(ModeloCamara):
    """`GET /deputados/{id}`. O CPF vem na resposta: nunca exposto nem serializado."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: int
    uri: str
    nomeCivil: str
    ultimoStatus: UltimoStatus
    cpf: str | None = Field(default=None, exclude=True, repr=False)
    sexo: str | None = None
    dataNascimento: date | None = None
    dataFalecimento: date | None = None
    ufNascimento: str | None = None
    municipioNascimento: str | None = None


class HistoricoDeputado(ModeloCamara):
    """Item de `GET /deputados/{id}/historico` (base de mandato/exercício/filiação, T-102)."""

    id: int
    nome: str
    nomeEleitoral: str | None = None
    siglaPartido: str | None = None
    siglaUf: str | None = None
    idLegislatura: int | None = None
    dataHora: datetime
    situacao: str | None = None  # observados: "Exercício", "Licença", "FIM_MANDATO", null
    condicaoEleitoral: str | None = None
    descricaoStatus: str | None = None
