"""Schemas de staging do Senado Federal — Dados Abertos (nomes originais da fonte).

Derivados de tests/fixtures/senado/ (coletados em 2026-11-02). Campos extras são aceitos sem
falhar; só declaramos o que o pipeline usa.

- `GET /votacao` (endpoint novo, decisão 013): lista JSON sem envelope, camelCase, com os votos
  embutidos. Só traz votações nominais (inclusive secretas) e não traz hora.
- `GET /senador/{codigo}`: formato derivado do XML (PascalCase, números como texto).
"""

from datetime import date

from pydantic import BaseModel, ConfigDict


class ModeloSenado(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)


class VotoSenado(ModeloSenado):
    codigoParlamentar: int
    nomeParlamentar: str
    sexoParlamentar: str | None = None
    siglaPartidoParlamentar: str | None = None  # "S/Partido" quando sem partido
    siglaUFParlamentar: str | None = None
    siglaVotoParlamentar: str  # ex.: "Sim", "Votou" (secreta), "AP", "P-NRV"
    descricaoVotoParlamentar: str | None = None  # ex.: "Atividade parlamentar"


class InformeLegislativo(ModeloSenado):
    siglaColegiado: str | None = None  # "PLEN"
    texto: str | None = None


class VotacaoSenado(ModeloSenado):
    """Item de `GET /votacao`."""

    codigoSessaoVotacao: int  # identificador da votação
    codigoSessao: int | None = None
    casaSessao: str | None = None  # "SF"
    dataSessao: date
    descricaoVotacao: str | None = None
    resultadoVotacao: str | None = None  # "A" aprovada, "R" rejeitada
    votacaoSecreta: str | None = None  # "S" | "N"
    totalVotosSim: int | None = None
    totalVotosNao: int | None = None
    totalVotosAbstencao: int | None = None
    # Matéria votada
    idProcesso: int | None = None
    codigoMateria: int | None = None
    sigla: str | None = None  # ex.: "PEC", "PLP", "MSF"
    numero: str | None = None
    ano: int | None = None
    identificacao: str | None = None  # ex.: "PEC 221/2019"
    ementa: str | None = None
    dataApresentacao: date | None = None
    informeLegislativo: InformeLegislativo | None = None
    votos: list[VotoSenado] = []


class IdentificacaoSenador(ModeloSenado):
    CodigoParlamentar: str
    NomeParlamentar: str
    NomeCompletoParlamentar: str
    SexoParlamentar: str | None = None  # "Masculino" | "Feminino"
    UrlFotoParlamentar: str | None = None
    SiglaPartidoParlamentar: str | None = None
    UfParlamentar: str | None = None


class DadosBasicosSenador(ModeloSenado):
    DataNascimento: date | None = None
    Naturalidade: str | None = None
    UfNaturalidade: str | None = None


class Senador(ModeloSenado):
    # Classes com nomes distintos dos campos: o campo sombrearia a classe na anotação.
    IdentificacaoParlamentar: IdentificacaoSenador
    DadosBasicosParlamentar: DadosBasicosSenador | None = None


class DetalheSenador(ModeloSenado):
    Parlamentar: Senador


class RespostaDetalheParlamentar(ModeloSenado):
    DetalheParlamentar: DetalheSenador
