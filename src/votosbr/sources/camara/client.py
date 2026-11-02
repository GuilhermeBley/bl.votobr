"""Cliente da API v2 da Câmara dos Deputados (seção 3.1)."""

from collections.abc import Iterator
from datetime import date, timedelta

from pydantic import TypeAdapter

from votosbr.config import Settings
from votosbr.domain.enums import FonteDado
from votosbr.sources.camara.schemas import (
    DeputadoDetalhe,
    DeputadoResumo,
    HistoricoDeputado,
    OrientacaoCamara,
    Resposta,
    VotacaoDetalhe,
    VotacaoResumo,
    VotoCamara,
)
from votosbr.sources.http import HttpClient, RawResponse
from votosbr.sources.raw_store import RawStore

BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
ID_ORGAO_PLENARIO = 180
ITENS_POR_PAGINA = 100


def criar_http_camara(settings: Settings, raw_store: RawStore) -> HttpClient:
    return HttpClient(
        fonte=FonteDado.CAMARA,
        base_url=BASE_URL,
        raw_store=raw_store,
        user_agent=settings.http_user_agent,
        max_rps=settings.http_max_rps_camara,
        timeout_s=settings.http_timeout_s,
        max_tentativas=settings.http_max_tentativas,
        backoff_inicial_s=settings.http_backoff_inicial_s,
        backoff_maximo_s=settings.http_backoff_maximo_s,
        headers={"Accept": "application/json"},
    )


def _parse[T](tipo: type[T], resposta: RawResponse) -> Resposta[T]:
    return TypeAdapter(Resposta[tipo]).validate_json(resposta.body)  # type: ignore[valid-type]


class CamaraClient:
    """Métodos devolvem o modelo de staging junto do `raw_documento_id` que o originou."""

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def votacoes(
        self, desde: date, ate: date, id_orgao: int = ID_ORGAO_PLENARIO
    ) -> Iterator[tuple[VotacaoResumo, int | None]]:
        """Votações com `data` em [desde, ate], ambos inclusivos.

        Na fonte, `dataFim` é exclusivo (observado em 2026-11-01: `dataInicio=dataFim=D` não
        retorna nada; `D..D+1` retorna só o dia D). Por isso pedimos `ate + 1` e filtramos.
        """
        params = {
            "dataInicio": desde.isoformat(),
            "dataFim": (ate + timedelta(days=1)).isoformat(),
            "idOrgao": id_orgao,
            "itens": ITENS_POR_PAGINA,
        }
        for pagina in self.http.paginate("/votacoes", params):
            for item in _parse(list[VotacaoResumo], pagina).dados:
                if desde <= item.data <= ate:
                    yield item, pagina.raw_documento_id

    def votacao(self, id_votacao: str) -> tuple[VotacaoDetalhe, int | None]:
        r = self.http.get(f"/votacoes/{id_votacao}")
        return _parse(VotacaoDetalhe, r).dados, r.raw_documento_id

    def votos(self, id_votacao: str) -> list[VotoCamara]:
        return _parse(list[VotoCamara], self.http.get(f"/votacoes/{id_votacao}/votos")).dados

    def orientacoes(self, id_votacao: str) -> list[OrientacaoCamara]:
        r = self.http.get(f"/votacoes/{id_votacao}/orientacoes")
        return _parse(list[OrientacaoCamara], r).dados

    def deputados(self, legislatura: int) -> Iterator[DeputadoResumo]:
        params = {"idLegislatura": legislatura, "itens": ITENS_POR_PAGINA}
        for pagina in self.http.paginate("/deputados", params):
            yield from _parse(list[DeputadoResumo], pagina).dados

    def deputado(self, id_deputado: int) -> tuple[DeputadoDetalhe, int | None]:
        r = self.http.get(f"/deputados/{id_deputado}")
        return _parse(DeputadoDetalhe, r).dados, r.raw_documento_id

    def historico(self, id_deputado: int) -> list[HistoricoDeputado]:
        r = self.http.get(f"/deputados/{id_deputado}/historico")
        return _parse(list[HistoricoDeputado], r).dados
