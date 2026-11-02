"""Fuso de referência: as fontes publicam horário de Brasília sem fuso explícito (seção 2.2)."""

from datetime import datetime
from zoneinfo import ZoneInfo

TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")


def em_brasilia(valor: datetime | None) -> datetime | None:
    """Anexa o fuso de Brasília a um datetime ingênuo; datetimes com fuso passam intactos."""
    if valor is None or valor.tzinfo is not None:
        return valor
    return valor.replace(tzinfo=TZ_BRASILIA)
