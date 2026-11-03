"""Regras de objeto com descrições reais da Câmara (out/2026) e do Senado (2026)."""

import pytest

from votosbr.domain.classificacao import ClassificadorObjeto, classificar_modalidade
from votosbr.domain.enums import VotacaoModalidade, VotacaoObjeto, VotoTipo


@pytest.mark.parametrize(
    ("descricao", "objeto"),
    [
        (
            "Aprovado, por unanimidade, o Requerimento de Urgência (Art. 155 do RICD).",
            VotacaoObjeto.URGENCIA,
        ),
        (
            "Aprovada a Redação Final, assinada pela relatora, Dep. Benedita da Silva (PT/RJ).",
            VotacaoObjeto.REDACAO_FINAL,
        ),
        ("Rejeitado o Requerimento.", VotacaoObjeto.REQUERIMENTO_PROCEDIMENTAL),
        (
            "Aprovado o Substitutivo ao Projeto de Decreto Legislativo nº 274, de 2026, adotado "
            "pela relatora da Comissão de Relações Exteriores e de Defesa Nacional.",
            VotacaoObjeto.TEXTO_BASE,
        ),
        (
            "Aprovada a Subemenda Substitutiva Global ao Projeto de Lei Complementar nº 186, de "
            "2026, adotada pelo relator da Comissão de Indústria, Comércio e Serviços, ressalvados "
            "os destaques. Sim: 461; Não: 4; Total: 465.",
            VotacaoObjeto.TEXTO_BASE,
        ),
        (
            "Votação nominal do Projeto de Lei Complementar nº 186, de 2026, nos termos do "
            "parecer.",
            VotacaoObjeto.TEXTO_BASE,
        ),
        (
            "Votação nominal da Proposta de Emenda à Constituição nº 221, de 2019, em primeiro "
            "turno.",
            VotacaoObjeto.TEXTO_BASE,
        ),
        (
            "Votação nominal da Emenda nº 8 (Substitutivo) ao Projeto de Lei nº 896, de 2023, nos "
            "termos do parecer, ressalvado o destaque.",
            VotacaoObjeto.TEXTO_BASE,
        ),
        (None, VotacaoObjeto.OUTRO),
        ("Texto sem padrão conhecido", VotacaoObjeto.OUTRO),
    ],
)
def test_objeto(classificador: ClassificadorObjeto, descricao: str | None, objeto: str) -> None:
    assert classificador.classificar(descricao).objeto == objeto


def test_turno(classificador: ClassificadorObjeto) -> None:
    c = classificador.classificar("Aprovada a Proposta de Emenda à Constituição em 2º turno")
    assert (c.objeto, c.turno) == (VotacaoObjeto.TEXTO_BASE, 2)


@pytest.mark.parametrize(
    ("votos", "tem_resultado", "esperado"),
    [
        ([VotoTipo.SIM, VotoTipo.NAO, VotoTipo.PRESIDENTE], True, VotacaoModalidade.NOMINAL),
        ([], True, VotacaoModalidade.SIMBOLICA),
        ([VotoTipo.SECRETO], True, VotacaoModalidade.SECRETA),
        ([], False, VotacaoModalidade.DESCONHECIDA),
        ([VotoTipo.PRESIDENTE], True, VotacaoModalidade.DESCONHECIDA),
    ],
)
def test_modalidade(votos: list[VotoTipo], tem_resultado: bool, esperado: str) -> None:
    assert classificar_modalidade(votos, tem_resultado=tem_resultado) == esperado
