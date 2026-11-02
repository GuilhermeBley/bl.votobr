"""Schemas da Câmara validam as fixtures reais; mappers puros produzem o core esperado."""

from datetime import date

from pydantic import TypeAdapter

from tests.conftest import carregar_fixture
from votosbr.domain.classificacao import ClassificadorObjeto
from votosbr.domain.enums import (
    BancadaTipo,
    OrientacaoTipo,
    VotacaoModalidade,
    VotacaoObjeto,
    VotoTipo,
)
from votosbr.domain.normalizacao import Normalizador
from votosbr.domain.tempo import TZ_BRASILIA
from votosbr.etl.mappers import camara as mapper
from votosbr.sources.camara.schemas import (
    DeputadoDetalhe,
    HistoricoDeputado,
    OrientacaoCamara,
    Resposta,
    VotacaoDetalhe,
    VotacaoResumo,
    VotoCamara,
)


def _resp[T](tipo: type[T], caminho: str) -> T:
    return TypeAdapter(Resposta[tipo]).validate_python(carregar_fixture(caminho)).dados  # type: ignore[valid-type]


def test_schemas_validam_todas_as_fixtures() -> None:
    assert _resp(list[VotacaoResumo], "camara/votacoes/plenario_pagina1.json")
    assert _resp(VotacaoDetalhe, "camara/votacao/nominal.json").proposicoesAfetadas
    assert _resp(VotacaoDetalhe, "camara/votacao/simbolica_urgencia.json")
    assert len(_resp(list[VotoCamara], "camara/votos/nominal.json")) == 466
    assert _resp(list[VotoCamara], "camara/votos/simbolica_vazia.json") == []
    assert _resp(list[OrientacaoCamara], "camara/orientacoes/nominal.json")
    assert _resp(list[HistoricoDeputado], "camara/historico/titular.json")


def test_cpf_nunca_serializado() -> None:
    d = _resp(DeputadoDetalhe, "camara/deputado/titular.json")
    assert "cpf" not in d.model_dump()
    assert "cpf" not in repr(d)


def _mapear_nominal(n: Normalizador, c: ClassificadorObjeto) -> mapper.VotacaoMapeada:
    return mapper.mapear_votacao(
        None,
        _resp(VotacaoDetalhe, "camara/votacao/nominal.json"),
        _resp(list[VotoCamara], "camara/votos/nominal.json"),
        _resp(list[OrientacaoCamara], "camara/orientacoes/nominal.json"),
        n,
        c,
    )


def test_mapear_votacao_nominal(
    normalizador: Normalizador, classificador: ClassificadorObjeto
) -> None:
    m = _mapear_nominal(normalizador, classificador)
    v = m.votacao
    assert v.id_publico == "camara-2635476-36"
    assert v.data == date(2026, 10, 14)
    assert v.data_hora is not None and v.data_hora.tzinfo == TZ_BRASILIA
    assert v.modalidade == VotacaoModalidade.NOMINAL
    assert v.objeto == VotacaoObjeto.TEXTO_BASE
    assert v.aprovado is True
    assert v.placar_fonte == {"Sim": 461, "Não": 4, "Total": 465}

    contagem = {t: sum(1 for x in m.votos if x.voto == t) for t in VotoTipo}
    assert (contagem[VotoTipo.SIM], contagem[VotoTipo.NAO], contagem[VotoTipo.PRESIDENTE]) == (
        461,
        4,
        1,
    )
    assert m.nao_mapeados == []
    assert [(p.sigla_tipo, p.numero, p.ano, papel) for p, papel in m.proposicoes] == [
        ("PLP", 186, 2026, "AFETADA")
    ]


def test_orientacao_vazia_e_ignorada_e_tipos_de_bancada(
    normalizador: Normalizador, classificador: ClassificadorObjeto
) -> None:
    m = _mapear_nominal(normalizador, classificador)
    por_sigla = {o.bancada_sigla: o for o in m.orientacoes}
    assert "AVANTE" not in por_sigla  # orientacaoVoto == ""
    assert len(m.orientacoes) == 11
    assert por_sigla["Governo"].bancada_tipo == BancadaTipo.GOVERNO
    assert por_sigla["Oposição"].bancada_tipo == BancadaTipo.OPOSICAO
    assert por_sigla["Fdr PT-PCdoB-PV"].bancada_tipo == BancadaTipo.FEDERACAO
    assert por_sigla["Bl UniPpPsd..."].bancada_tipo == BancadaTipo.BLOCO
    assert por_sigla["PL"].bancada_tipo == BancadaTipo.PARTIDO
    assert por_sigla["MISSÃO"].orientacao == OrientacaoTipo.NAO


def test_mapear_simbolica_com_objeto(
    normalizador: Normalizador, classificador: ClassificadorObjeto
) -> None:
    detalhe = _resp(VotacaoDetalhe, "camara/votacao/simbolica_urgencia.json")
    resumo = VotacaoResumo.model_validate(
        {
            **detalhe.model_dump(
                include={"id", "uri", "data", "siglaOrgao", "descricao", "aprovacao"}
            ),
            "proposicaoObjeto": "REQ 4194/2026",
            "uriProposicaoObjeto": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/2645996",
        }
    )
    m = mapper.mapear_votacao(resumo, detalhe, [], [], normalizador, classificador)
    assert m.votacao.modalidade == VotacaoModalidade.SIMBOLICA
    assert m.votacao.objeto == VotacaoObjeto.URGENCIA
    papeis = {(p.sigla_tipo, p.numero, p.ano): papel for p, papel in m.proposicoes}
    assert papeis == {("PL", 3099, 2019): "AFETADA", ("REQ", 4194, 2026): "OBJETO"}


def test_mapear_pessoa() -> None:
    p = mapper.mapear_pessoa(_resp(DeputadoDetalhe, "camara/deputado/titular.json"))
    assert p.slug_base == "marx-beltrao-al"
    assert p.nome_busca == "marx beltrao"
