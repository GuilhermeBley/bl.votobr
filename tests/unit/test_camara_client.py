from datetime import date
from pathlib import Path

import httpx
import respx

from tests.conftest import carregar_fixture
from votosbr.domain.enums import FonteDado
from votosbr.sources.camara.client import BASE_URL, CamaraClient
from votosbr.sources.http import HttpClient
from votosbr.sources.raw_store import RawStore


@respx.mock
def test_votacoes_compensa_data_fim_exclusiva_da_fonte(tmp_path: Path) -> None:
    # Coletada com dataInicio=27, dataFim=28: só traz o dia 27 (dataFim exclusivo).
    pagina = carregar_fixture("camara/votacoes/plenario_pagina1.json")
    pagina["links"] = []
    fora_do_intervalo = {**pagina["dados"][0], "id": "1-1", "data": "2026-10-28"}
    pagina["dados"].append(fora_do_intervalo)
    rota = respx.get(f"{BASE_URL}/votacoes").mock(return_value=httpx.Response(200, json=pagina))

    http = HttpClient(
        fonte=FonteDado.CAMARA,
        base_url=BASE_URL,
        raw_store=RawStore(tmp_path),
        user_agent="teste",
        max_rps=0,
    )
    itens = [v for v, _ in CamaraClient(http).votacoes(date(2026, 10, 27), date(2026, 10, 27))]

    params = rota.calls[0].request.url.params
    assert (params["dataInicio"], params["dataFim"]) == ("2026-10-27", "2026-10-28")
    assert itens and all(v.data == date(2026, 10, 27) for v in itens)
