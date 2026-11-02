"""LexML Brasil: URN como chave canônica da norma (seção 3.4). Implementação em T-302."""

from datetime import date


def urn_lei_federal(numero: int, data_assinatura: date) -> str:
    """Ex.: Lei 12.965 de 23/04/2014 -> `urn:lex:br:federal:lei:2014-04-23;12965`."""
    return f"urn:lex:br:federal:lei:{data_assinatura.isoformat()};{numero}"
