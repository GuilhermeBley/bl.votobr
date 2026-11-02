"""Cliente HTTP base: retry, ausência de retry em 4xx, paginação e RawStore."""

import gzip
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx

from tests.conftest import carregar_fixture
from votosbr.domain.enums import FonteDado
from votosbr.sources.http import ErroFonte, HttpClient, recurso_do_path
from votosbr.sources.raw_store import RawStore

BASE = "https://api.exemplo.gov.br/v2"


class RegistroFalso:
    def __init__(self) -> None:
        self.registros: list[dict[str, object]] = []

    def registrar(self, **kwargs: object) -> int:
        self.registros.append(kwargs)
        return len(self.registros)


@pytest.fixture
def registro() -> RegistroFalso:
    return RegistroFalso()


@pytest.fixture
def cliente(tmp_path: Path, registro: RegistroFalso) -> Iterator[HttpClient]:
    c = HttpClient(
        fonte=FonteDado.CAMARA,
        base_url=BASE,
        raw_store=RawStore(tmp_path, registro),
        user_agent="VotosBR-teste",
        max_rps=0,
        max_tentativas=3,
        backoff_inicial_s=0,
        backoff_maximo_s=0,
    )
    yield c
    c.close()


@respx.mock
def test_retry_em_5xx_e_grava_raw(
    cliente: HttpClient, registro: RegistroFalso, tmp_path: Path
) -> None:
    corpo = b'{"dados": []}'
    rota = respx.get(f"{BASE}/votacoes/1-2/votos").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, content=corpo, headers={"content-type": "application/json"}),
        ]
    )
    r = cliente.get("/votacoes/1-2/votos")
    assert rota.call_count == 2
    assert r.raw_documento_id == 1
    assert rota.calls[-1].request.headers["User-Agent"] == "VotosBR-teste"

    reg = registro.registros[0]
    sha = hashlib.sha256(corpo).hexdigest()
    assert reg["conteudo_hash"] == sha
    assert str(reg["caminho_storage"]).startswith("camara/votacoes_votos/")
    assert gzip.decompress((tmp_path / str(reg["caminho_storage"])).read_bytes()) == corpo


@respx.mock
def test_sem_retry_em_404_mas_resposta_gravada(
    cliente: HttpClient, registro: RegistroFalso
) -> None:
    rota = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(404, json={"erro": 1}))
    with pytest.raises(ErroFonte) as exc:
        cliente.get("/x")
    assert exc.value.status == 404
    assert rota.call_count == 1
    assert registro.registros[0]["http_status"] == 404


@respx.mock
def test_desiste_apos_max_tentativas(cliente: HttpClient) -> None:
    rota = respx.get(f"{BASE}/x").mock(side_effect=httpx.ConnectTimeout("timeout"))
    with pytest.raises(ErroFonte):
        cliente.get("/x")
    assert rota.call_count == 3


@respx.mock
def test_paginacao_segue_links_next(cliente: HttpClient) -> None:
    pagina1 = carregar_fixture("camara/votacoes/plenario_pagina1.json")
    proxima = next(link["href"] for link in pagina1["links"] if link["rel"] == "next")
    # A fixture real aponta para dadosabertos.camara.leg.br; reapontamos para a base do teste.
    pagina1["links"] = [{"rel": "next", "href": f"{BASE}/votacoes?pagina=2"}]
    respx.get(f"{BASE}/votacoes", params={"pagina": "2"}).mock(
        return_value=httpx.Response(200, json={"dados": [], "links": []})
    )
    respx.get(f"{BASE}/votacoes", params={"itens": "3"}).mock(
        return_value=httpx.Response(200, json=pagina1)
    )
    paginas = list(cliente.paginate("/votacoes", {"itens": 3}))
    assert len(paginas) == 2
    assert "pagina=2" in proxima
    assert json.loads(paginas[0].body)["dados"]


def test_recurso_do_path() -> None:
    assert recurso_do_path("/votacoes/2265603-43/votos") == "votacoes_votos"
    assert recurso_do_path("/deputados/178843") == "deputados"
