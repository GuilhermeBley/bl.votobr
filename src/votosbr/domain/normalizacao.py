"""Normalização de votos e orientações a partir dos YAMLs versionados (seção 5.4).

O valor original nunca é alterado: o chamador guarda `original` ao lado do normalizado.
Valor desconhecido vira OUTRO e é sinalizado (`mapeado=False`) para registro em
`valor_nao_mapeado`; nunca derruba a carga.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Generic, TypeVar

import yaml

from votosbr.domain.enums import FonteDado, OrientacaoTipo, VotoTipo
from votosbr.domain.texto import chave_comparacao

E = TypeVar("E", bound=StrEnum)


@dataclass(frozen=True)
class Normalizado(Generic[E]):
    valor: E
    original: str
    mapeado: bool


class TabelaMapeamento(Generic[E]):
    def __init__(self, enum: type[E], por_fonte: dict[FonteDado | None, dict[str, E]]) -> None:
        self._enum = enum
        self._por_fonte = por_fonte

    @classmethod
    def de_yaml(cls, enum: type[E], caminho: Path) -> "TabelaMapeamento[E]":
        """Formato: `{FONTE|"*": {valor_original: VALOR_ENUM}}`. `"*"` vale para qualquer fonte."""
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
        por_fonte: dict[FonteDado | None, dict[str, E]] = {}
        for fonte, valores in dados.items():
            chave_fonte = None if fonte == "*" else FonteDado(fonte)
            por_fonte[chave_fonte] = {
                chave_comparacao(str(original)): enum(destino)
                for original, destino in (valores or {}).items()
            }
        return cls(enum, por_fonte)

    def normalizar(self, fonte: FonteDado, original: str) -> Normalizado[E]:
        chave = chave_comparacao(original)
        for tabela in (self._por_fonte.get(fonte, {}), self._por_fonte.get(None, {})):
            if chave in tabela:
                return Normalizado(tabela[chave], original, mapeado=True)
        return Normalizado(self._enum("OUTRO"), original, mapeado=False)


@dataclass(frozen=True)
class Normalizador:
    votos: TabelaMapeamento[VotoTipo]
    orientacoes: TabelaMapeamento[OrientacaoTipo]

    @classmethod
    def carregar(cls, diretorio: Path) -> "Normalizador":
        return cls(
            votos=TabelaMapeamento.de_yaml(VotoTipo, diretorio / "votos.yaml"),
            orientacoes=TabelaMapeamento.de_yaml(OrientacaoTipo, diretorio / "orientacoes.yaml"),
        )

    def voto(self, fonte: FonteDado, original: str) -> Normalizado[VotoTipo]:
        return self.votos.normalizar(fonte, original)

    def orientacao(self, fonte: FonteDado, original: str) -> Normalizado[OrientacaoTipo]:
        return self.orientacoes.normalizar(fonte, original)
