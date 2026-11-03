from datetime import date
from pathlib import Path

import httpx
import respx
from pydantic import TypeAdapter

from tests.conftest import carregar_fixture
from votosbr.domain.classificacao import ClassificadorObjeto
from votosbr.domain.enums import Casa, FonteDado, VotacaoModalidade, VotoTipo
from votosbr.domain.normalizacao import Normalizador
from votosbr.etl.mappers import senado as mapper
from votosbr.sources.http import HttpClient
from votosbr.sources.raw_store import RawStore
from votosbr.sources.senado.client import BASE_URL, SenadoClient
from votosbr.sources.senado.schemas import RespostaDetalheParlamentar, VotacaoSenado

FIXTURE = "senado/votacoes/plenario_20260901_20261031.json"


def _votacoes() -> dict[int, VotacaoSenado]:
    itens = TypeAdapter(list[VotacaoSenado]).validate_python(carregar_fixture(FIXTURE))
    return {v.codigoSessaoVotacao: v for v in itens}


def test_votacao_nominal(normalizador: Normalizador, classificador: ClassificadorObjeto) -> None:
    m = mapper.mapear_votacao(_votacoes()[7106], normalizador, classificador)  # PEC 221/2019

    v = m.votacao
    assert (v.id_publico, v.casa, v.fonte, v.orgao_sigla) == (
        "senado-7106",
        Casa.SENADO,
        FonteDado.SENADO,
        "PLEN",
    )
    assert v.data == date(2026, 10, 14) and v.data_hora is None
    assert v.modalidade == VotacaoModalidade.NOMINAL
    assert v.aprovado is True and v.resultado_fonte == "A"
    assert len(m.votos) == 81 and not m.nao_mapeados and not m.orientacoes

    [(proposicao, papel)] = m.proposicoes
    assert papel == "OBJETO"
    assert (proposicao.id_externo, proposicao.sigla_tipo, proposicao.numero, proposicao.ano) == (
        "9056435",
        "PEC",
        221,
        2019,
    )


def test_votacao_secreta_com_placar(
    normalizador: Normalizador, classificador: ClassificadorObjeto
) -> None:
    m = mapper.mapear_votacao(_votacoes()[7104], normalizador, classificador)  # PDL 995/2026

    assert m.votacao.modalidade == VotacaoModalidade.SECRETA
    assert m.votacao.placar_fonte == {"Sim": 63, "Não": 4, "Abstenção": 0}
    assert {v.voto for v in m.votos} >= {VotoTipo.SECRETO}


def test_sem_partido_nao_vira_sigla(
    normalizador: Normalizador, classificador: ClassificadorObjeto
) -> None:
    for votacao in _votacoes().values():
        m = mapper.mapear_votacao(votacao, normalizador, classificador)
        originais = {v.codigoParlamentar: v.siglaPartidoParlamentar for v in votacao.votos}
        for voto in m.votos:
            if originais[int(voto.id_externo_pessoa)] == "S/Partido":
                assert voto.partido_sigla_fonte is None


def test_pessoa() -> None:
    corpo = carregar_fixture("senado/senador/5672.json")
    parlamentar = RespostaDetalheParlamentar.model_validate(corpo).DetalheParlamentar.Parlamentar

    p = mapper.mapear_pessoa(parlamentar)

    assert (p.nome_parlamentar, p.nome_civil, p.sexo) == ("Alan Rick", "Alan Rick Miranda", "M")
    assert (p.data_nascimento, p.uf_nascimento) == (date(1976, 10, 23), "AC")
    assert p.slug_base.startswith("alan-rick")


@respx.mock
def test_cliente_envia_data_fim_inclusiva_e_filtra(tmp_path: Path) -> None:
    rota = respx.get(f"{BASE_URL}/votacao").mock(
        return_value=httpx.Response(200, json=carregar_fixture(FIXTURE))
    )
    http = HttpClient(
        fonte=FonteDado.SENADO,
        base_url=BASE_URL,
        raw_store=RawStore(tmp_path),
        user_agent="teste",
        max_rps=0,
    )

    itens = SenadoClient(http).votacoes(date(2026, 10, 14), date(2026, 10, 14))

    params = rota.calls[0].request.url.params
    assert (params["dataInicio"], params["dataFim"]) == ("2026-10-14", "2026-10-14")
    assert sorted(v.codigoSessaoVotacao for v, _ in itens) == [7106, 7107]
