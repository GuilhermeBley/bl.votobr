"""Cliente do Senado Federal — Dados Abertos (seção 3.2).

Os endpoints ainda não foram validados (T-201): antes de adicionar métodos, coletar fixtures
em tests/fixtures/senado/ e decidir entre endpoints novos ("processo", "votacao") e legados
("materia", "plenario/lista/votacao"), registrando a decisão na seção 13. Os legados devem
ficar isolados num adaptador próprio.
"""

from votosbr.config import Settings
from votosbr.domain.enums import FonteDado
from votosbr.sources.http import HttpClient
from votosbr.sources.raw_store import RawStore

BASE_URL = "https://legis.senado.leg.br/dadosabertos"


def criar_http_senado(settings: Settings, raw_store: RawStore) -> HttpClient:
    return HttpClient(
        fonte=FonteDado.SENADO,
        base_url=BASE_URL,
        raw_store=raw_store,
        user_agent=settings.http_user_agent,
        max_rps=settings.http_max_rps_senado,
        timeout_s=settings.http_timeout_s,
        max_tentativas=settings.http_max_tentativas,
        backoff_inicial_s=settings.http_backoff_inicial_s,
        backoff_maximo_s=settings.http_backoff_maximo_s,
        headers={"Accept": "application/json"},
    )


class SenadoClient:
    def __init__(self, http: HttpClient) -> None:
        self.http = http
