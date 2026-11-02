"""Utilitários de texto puros: comparação sem acento/caixa e geração de slugs."""

import re
import unicodedata

_ESPACOS = re.compile(r"\s+")
_NAO_SLUG = re.compile(r"[^a-z0-9]+")


def sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def chave_comparacao(texto: str) -> str:
    """Forma canônica para comparar valores da fonte: sem acentos, minúscula, espaços colapsados."""
    return _ESPACOS.sub(" ", sem_acentos(texto).strip().lower())


def slugificar(*partes: str) -> str:
    texto = chave_comparacao(" ".join(partes))
    return _NAO_SLUG.sub("-", texto).strip("-")
