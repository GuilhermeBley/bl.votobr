"""Envelope, paginação e tipos comuns do contrato (seção 7.1). Separados dos modelos ORM."""

import math
from datetime import UTC, datetime
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, Field, PlainSerializer

T = TypeVar("T")


def _iso_utc(valor: datetime) -> str:
    return valor.astimezone(UTC).isoformat().replace("+00:00", "Z")


# Data/hora sempre em ISO 8601 UTC com "Z"; o frontend converte para Brasília.
DataHoraUTC = Annotated[datetime, PlainSerializer(_iso_utc, return_type=str)]


class Paginacao(BaseModel):
    pagina: int
    por_pagina: int
    total: int
    total_paginas: int

    @classmethod
    def calcular(cls, pagina: int, por_pagina: int, total: int) -> "Paginacao":
        return cls(
            pagina=pagina,
            por_pagina=por_pagina,
            total=total,
            total_paginas=math.ceil(total / por_pagina) if total else 0,
        )


class Meta(BaseModel):
    gerado_em: DataHoraUTC = Field(default_factory=lambda: datetime.now(UTC))
    paginacao: Paginacao | None = None


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Meta = Field(default_factory=Meta)


class FonteOut(BaseModel):
    nome: str
    url: str | None
    coletado_em: DataHoraUTC | None


class Aviso(BaseModel):
    codigo: str
    mensagem: str


NOME_FONTE = {
    "CAMARA": "Câmara dos Deputados – Dados Abertos",
    "SENADO": "Senado Federal – Dados Abertos",
    "CONGRESSO": "Congresso Nacional",
    "LEXML": "LexML Brasil",
}
