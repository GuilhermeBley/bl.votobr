import pytest

from tests.conftest import carregar_fixture
from votosbr.domain.enums import FonteDado, OrientacaoTipo, VotoTipo
from votosbr.domain.normalizacao import Normalizador


def test_todos_os_votos_das_fixtures_da_camara_mapeados(normalizador: Normalizador) -> None:
    votos = carregar_fixture("camara/votos/nominal.json")["dados"]
    for v in votos:
        assert normalizador.voto(FonteDado.CAMARA, v["tipoVoto"]).mapeado, v["tipoVoto"]


def test_todas_as_orientacoes_nao_vazias_mapeadas(normalizador: Normalizador) -> None:
    for o in carregar_fixture("camara/orientacoes/nominal.json")["dados"]:
        if o["orientacaoVoto"]:
            assert normalizador.orientacao(FonteDado.CAMARA, o["orientacaoVoto"]).mapeado


@pytest.mark.parametrize(
    ("fonte", "original", "esperado"),
    [
        (FonteDado.CAMARA, "Sim", VotoTipo.SIM),
        (FonteDado.CAMARA, " não ", VotoTipo.NAO),
        (FonteDado.CAMARA, "Artigo 17", VotoTipo.PRESIDENTE),
        (FonteDado.SENADO, "P-NRV", VotoTipo.PRESENTE_SEM_VOTO),
        (FonteDado.SENADO, "MIS", VotoTipo.AUSENTE_JUSTIFICADO),
        (FonteDado.SENADO, "Votou", VotoTipo.SECRETO),
    ],
)
def test_mapeamento(
    normalizador: Normalizador, fonte: FonteDado, original: str, esperado: VotoTipo
) -> None:
    n = normalizador.voto(fonte, original)
    assert n.valor == esperado
    assert n.original == original  # original preservado sem alteração


def test_valor_desconhecido_vira_outro_sem_excecao(normalizador: Normalizador) -> None:
    n = normalizador.voto(FonteDado.CAMARA, "Valor Inédito")
    assert (n.valor, n.mapeado) == (VotoTipo.OUTRO, False)


def test_sigla_do_senado_nao_vale_para_a_camara(normalizador: Normalizador) -> None:
    assert not normalizador.voto(FonteDado.CAMARA, "P-NRV").mapeado


def test_orientacao_coringa_vale_para_qualquer_fonte(normalizador: Normalizador) -> None:
    assert normalizador.orientacao(FonteDado.SENADO, "Liberado").valor == OrientacaoTipo.LIBERADO
