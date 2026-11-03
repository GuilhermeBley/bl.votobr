"""Cliente do Senado Federal — Dados Abertos (seção 3.2).

Endpoints validados em 2026-11-02 (fixtures em tests/fixtures/senado/):
- `GET /votacao?dataInicio=&dataFim=`: endpoint novo de votações de Plenário (decisão 013). O
  legado `/plenario/lista/votacao` informa desativação prevista para 2026-02-01 e aponta para
  este. Aqui `dataFim` é inclusivo (diferente da Câmara) e intervalos de meses são aceitos.
- `GET /senador/{codigo}`: detalhe do parlamentar.

A API oscila (timeouts de conexão intermitentes); o retry do `HttpClient` cobre isso.
"""

from datetime import date

from pydantic import TypeAdapter

from votosbr.config import Settings
from votosbr.domain.enums import FonteDado
from votosbr.sources.http import HttpClient
from votosbr.sources.raw_store import RawStore
from votosbr.sources.senado.schemas import RespostaDetalheParlamentar, Senador, VotacaoSenado

BASE_URL = "https://legis.senado.leg.br/dadosabertos"

_LISTA_VOTACOES = TypeAdapter(list[VotacaoSenado])


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
    """Métodos devolvem o modelo de staging junto do `raw_documento_id` que o originou."""

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def votacoes(self, desde: date, ate: date) -> list[tuple[VotacaoSenado, int | None]]:
        """Votações com `dataSessao` em [desde, ate], ambos inclusivos (como na fonte)."""
        r = self.http.get("/votacao", {"dataInicio": desde.isoformat(), "dataFim": ate.isoformat()})
        return [
            (v, r.raw_documento_id)
            for v in _LISTA_VOTACOES.validate_json(r.body)
            if desde <= v.dataSessao <= ate
        ]

    def senador(self, codigo: int) -> tuple[Senador, int | None]:
        r = self.http.get(f"/senador/{codigo}")
        resposta = RespostaDetalheParlamentar.model_validate_json(r.body)
        return resposta.DetalheParlamentar.Parlamentar, r.raw_documento_id
