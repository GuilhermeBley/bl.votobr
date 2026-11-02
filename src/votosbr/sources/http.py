"""Cliente HTTP base: timeout, retry com backoff e jitter, limite de taxa por fonte e paginação.

- Retry (tenacity) só para 429, 5xx e erros de transporte/timeout; demais 4xx falham na hora.
- Toda resposta final (inclusive de erro) passa pelo RawStore antes de qualquer parse.
"""

import json
import re
import threading
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import structlog
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from votosbr.domain.enums import FonteDado
from votosbr.sources.raw_store import RawStore

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RawResponse:
    url: str
    status: int
    body: bytes
    content_type: str
    raw_documento_id: int | None

    def json(self) -> Any:
        return json.loads(self.body)


class FonteClient(Protocol):
    fonte: FonteDado

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> RawResponse: ...

    def paginate(
        self, path: str, params: Mapping[str, Any] | None = None
    ) -> Iterator[RawResponse]: ...


class ErroFonte(Exception):
    def __init__(self, mensagem: str, *, url: str, status: int | None = None) -> None:
        super().__init__(mensagem)
        self.url = url
        self.status = status


class ErroTransitorio(ErroFonte):
    """429, 5xx, timeout ou falha de conexão: elegível a retry."""


class LimitadorTaxa:
    """Intervalo mínimo entre requisições (thread-safe). `rps <= 0` desliga o limite."""

    def __init__(self, rps: float) -> None:
        self._intervalo = 1.0 / rps if rps > 0 else 0.0
        self._proxima = 0.0
        self._trava = threading.Lock()

    def aguardar(self) -> None:
        with self._trava:
            agora = time.monotonic()
            espera = self._proxima - agora
            self._proxima = max(agora, self._proxima) + self._intervalo
        if espera > 0:
            time.sleep(espera)


_SEGMENTO_ID = re.compile(r"\d")


def recurso_do_path(path: str) -> str:
    """`/votacoes/2265603-43/votos` -> `votacoes_votos` (segmentos com dígitos são ids)."""
    partes = [p for p in path.strip("/").split("/") if p and not _SEGMENTO_ID.search(p)]
    return "_".join(partes) or "raiz"


class HttpClient:
    def __init__(
        self,
        *,
        fonte: FonteDado,
        base_url: str,
        raw_store: RawStore,
        user_agent: str,
        max_rps: float,
        timeout_s: float = 30.0,
        max_tentativas: int = 5,
        backoff_inicial_s: float = 1.0,
        backoff_maximo_s: float = 60.0,
        headers: Mapping[str, str] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.fonte = fonte
        self.base_url = base_url.rstrip("/")
        self.raw_store = raw_store
        self._limitador = LimitadorTaxa(max_rps)
        self._max_tentativas = max_tentativas
        self._backoff_inicial_s = backoff_inicial_s
        self._backoff_maximo_s = backoff_maximo_s
        self._client = client or httpx.Client(timeout=timeout_s)
        self._headers = {"User-Agent": user_agent, **(headers or {})}

    def close(self) -> None:
        self._client.close()

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> RawResponse:
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        recurso = recurso_do_path(httpx.URL(url).path.removeprefix(httpx.URL(self.base_url).path))
        retrying = Retrying(
            retry=retry_if_exception_type(ErroTransitorio),
            wait=wait_exponential_jitter(
                multiplier=self._backoff_inicial_s,
                jitter=self._backoff_inicial_s,
                max=self._backoff_maximo_s,
            ),
            stop=stop_after_attempt(self._max_tentativas),
            reraise=True,
        )
        resposta: httpx.Response | None = None
        for tentativa in retrying:
            with tentativa:
                resposta = self._requisitar(url, params)
        assert resposta is not None

        raw_id = self.raw_store.gravar(
            fonte=self.fonte,
            recurso=recurso,
            url=str(resposta.request.url),
            parametros=params,
            http_status=resposta.status_code,
            corpo=resposta.content,
            content_type=resposta.headers.get("content-type", ""),
        )
        if resposta.is_error:
            raise ErroFonte(
                f"{self.fonte} respondeu {resposta.status_code}",
                url=str(resposta.request.url),
                status=resposta.status_code,
            )
        return RawResponse(
            url=str(resposta.request.url),
            status=resposta.status_code,
            body=resposta.content,
            content_type=resposta.headers.get("content-type", ""),
            raw_documento_id=raw_id,
        )

    def _requisitar(self, url: str, params: Mapping[str, Any] | None) -> httpx.Response:
        self._limitador.aguardar()
        try:
            resposta = self._client.get(url, params=params, headers=self._headers)
        except httpx.TransportError as exc:  # inclui timeouts
            log.warning("http.erro_transporte", url=url, erro=repr(exc))
            raise ErroTransitorio(repr(exc), url=url) from exc
        if resposta.status_code == 429 or resposta.status_code >= 500:
            log.warning(
                "http.status_transitorio", url=str(resposta.url), status=resposta.status_code
            )
            raise ErroTransitorio(
                f"status {resposta.status_code}", url=str(resposta.url), status=resposta.status_code
            )
        return resposta

    def paginate(self, path: str, params: Mapping[str, Any] | None = None) -> Iterator[RawResponse]:
        """Segue `links[rel=next]` (padrão da Câmara). Fontes sem `links` retornam uma página."""
        resposta = self.get(path, params)
        yield resposta
        while proxima := _link_next(resposta):
            resposta = self.get(proxima)  # a URL de `next` já carrega os parâmetros
            yield resposta


def _link_next(resposta: RawResponse) -> str | None:
    if "json" not in resposta.content_type:
        return None
    corpo = resposta.json()
    links = corpo.get("links", []) if isinstance(corpo, dict) else []
    return next((link["href"] for link in links if link.get("rel") == "next"), None)
