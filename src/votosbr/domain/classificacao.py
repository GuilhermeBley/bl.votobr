"""Classificação de votações: objeto (regras em YAML) e modalidade (seção 6.7). Funções puras."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from votosbr.domain.enums import VOTOS_COM_SENTIDO, VotacaoModalidade, VotacaoObjeto, VotoTipo
from votosbr.domain.texto import chave_comparacao


@dataclass(frozen=True)
class RegraObjeto:
    objeto: VotacaoObjeto
    padroes: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class Classificacao:
    objeto: VotacaoObjeto
    turno: int | None


_TURNO = re.compile(r"\b(primeiro|1o|1)\s+turno|\b(segundo|2o|2)\s+turno")


class ClassificadorObjeto:
    """Regras avaliadas em ordem sobre a descrição normalizada; a primeira que casar vence."""

    def __init__(self, regras: Iterable[RegraObjeto]) -> None:
        self.regras = tuple(regras)

    @classmethod
    def de_yaml(cls, caminho: Path) -> "ClassificadorObjeto":
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or []
        return cls(
            RegraObjeto(
                objeto=VotacaoObjeto(item["objeto"]),
                padroes=tuple(re.compile(p) for p in item["padroes"]),
            )
            for item in dados
        )

    def classificar(self, descricao: str | None) -> Classificacao:
        if not descricao:
            return Classificacao(VotacaoObjeto.OUTRO, None)
        texto = chave_comparacao(descricao)
        objeto = next(
            (r.objeto for r in self.regras if any(p.search(texto) for p in r.padroes)),
            VotacaoObjeto.OUTRO,
        )
        return Classificacao(objeto, extrair_turno(texto))


def extrair_turno(texto_normalizado: str) -> int | None:
    m = _TURNO.search(texto_normalizado)
    if not m:
        return None
    return 1 if m.group(1) else 2


def classificar_modalidade(
    votos: Iterable[VotoTipo], *, tem_resultado: bool, secreta_na_fonte: bool = False
) -> VotacaoModalidade:
    tipos = set(votos)
    if secreta_na_fonte or VotoTipo.SECRETO in tipos:
        return VotacaoModalidade.SECRETA
    if tipos & VOTOS_COM_SENTIDO:
        return VotacaoModalidade.NOMINAL
    if not tipos and tem_resultado:
        return VotacaoModalidade.SIMBOLICA
    return VotacaoModalidade.DESCONHECIDA
