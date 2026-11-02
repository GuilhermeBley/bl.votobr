"""API da Câmara simulada com respx a partir das fixtures reais.

Duas votações: uma nominal (2635476-36) e uma simbólica (2645996-7). Os detalhes de deputados
são sintetizados a partir de `deputado_` dos votos usando a fixture real de um deputado como
molde (só há uma fixture de `/deputados/{id}`).
"""

import copy
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import respx
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import carregar_fixture
from votosbr.config import RAIZ_PROJETO, Settings
from votosbr.etl.controle import Execucao
from votosbr.etl.jobs import seed
from votosbr.etl.jobs.camara_votacoes import JobCamaraVotacoes
from votosbr.etl.jobs.contexto import ContextoJob
from votosbr.sources.camara.client import BASE_URL

ID_NOMINAL = "2635476-36"
ID_SIMBOLICA = "2645996-7"


class CamaraFalsa:
    def __init__(self) -> None:
        self.votos_nominal: dict[str, Any] = carregar_fixture("camara/votos/nominal.json")
        self.falhar_detalhe: set[str] = set()
        self._molde_deputado = carregar_fixture("camara/deputado/titular.json")
        self._deputados = {
            v["deputado_"]["id"]: v["deputado_"] for v in self.votos_nominal["dados"]
        }

    def listagem(self) -> dict[str, Any]:
        nominal = carregar_fixture("camara/votacao/nominal.json")["dados"]
        simbolica = carregar_fixture("camara/votacao/simbolica_urgencia.json")["dados"]
        campos = (
            "id",
            "uri",
            "data",
            "dataHoraRegistro",
            "siglaOrgao",
            "uriOrgao",
            "uriEvento",
            "descricao",
            "aprovacao",
        )
        return {
            "dados": [
                {
                    **{k: nominal[k] for k in campos},
                    "proposicaoObjeto": None,
                    "uriProposicaoObjeto": None,
                },
                {
                    **{k: simbolica[k] for k in campos},
                    "proposicaoObjeto": "REQ 4194/2026",
                    "uriProposicaoObjeto": f"{BASE_URL}/proposicoes/2645996",
                },
            ],
            "links": [],
        }

    def deputado(self, id_deputado: int) -> dict[str, Any]:
        resumo = self._deputados[id_deputado]
        corpo = copy.deepcopy(self._molde_deputado)
        corpo["dados"]["id"] = id_deputado
        corpo["dados"]["nomeCivil"] = resumo["nome"]
        corpo["dados"]["ultimoStatus"].update(
            id=id_deputado,
            nome=resumo["nome"],
            siglaUf=resumo["siglaUf"],
            siglaPartido=resumo["siglaPartido"],
            urlFoto=resumo["urlFoto"],
        )
        return corpo

    def _votacao(self, request: httpx.Request, id_votacao: str) -> httpx.Response:
        if id_votacao in self.falhar_detalhe:
            return httpx.Response(404, json={"status": 404})
        nome = "nominal" if id_votacao == ID_NOMINAL else "simbolica_urgencia"
        return httpx.Response(200, json=carregar_fixture(f"camara/votacao/{nome}.json"))

    def _votos(self, request: httpx.Request, id_votacao: str) -> httpx.Response:
        if id_votacao == ID_NOMINAL:
            return httpx.Response(200, json=self.votos_nominal)
        return httpx.Response(200, json=carregar_fixture("camara/votos/simbolica_vazia.json"))

    def _orientacoes(self, request: httpx.Request, id_votacao: str) -> httpx.Response:
        nome = "nominal" if id_votacao == ID_NOMINAL else "simbolica"
        return httpx.Response(200, json=carregar_fixture(f"camara/orientacoes/{nome}.json"))

    def _deputado(self, request: httpx.Request, id_deputado: str) -> httpx.Response:
        return httpx.Response(200, json=self.deputado(int(id_deputado)))

    @contextmanager
    def ativa(self) -> Iterator[respx.MockRouter]:
        base = re.escape(BASE_URL)
        with respx.mock(assert_all_called=False) as router:
            router.get(url__regex=rf"{base}/votacoes\?").mock(
                side_effect=lambda r: httpx.Response(200, json=self.listagem())
            )
            router.get(url__regex=rf"{base}/votacoes/(?P<id_votacao>[\d-]+)/votos").mock(
                side_effect=self._votos
            )
            router.get(url__regex=rf"{base}/votacoes/(?P<id_votacao>[\d-]+)/orientacoes").mock(
                side_effect=self._orientacoes
            )
            router.get(url__regex=rf"{base}/votacoes/(?P<id_votacao>[\d-]+)$").mock(
                side_effect=self._votacao
            )
            router.get(url__regex=rf"{base}/deputados/(?P<id_deputado>\d+)$").mock(
                side_effect=self._deputado
            )
            yield router


def settings_teste(tmp_path: Path) -> Settings:
    return Settings(
        raw_store_path=tmp_path / "raw",
        http_max_rps_camara=0,
        http_backoff_inicial_s=0,
        http_max_tentativas=2,
        dir_seeds=RAIZ_PROJETO / "seeds",
        dir_normalizacao=RAIZ_PROJETO / "normalizacao",
    )


def rodar_seed(fabrica: sessionmaker[Session], cfg: Settings) -> None:
    with Execucao(fabrica, seed.JOB, {}) as ex:
        seed.executar(ContextoJob(cfg, fabrica, ex))


def rodar_fatia(
    fabrica: sessionmaker[Session], cfg: Settings, camara: CamaraFalsa
) -> tuple[bool, Execucao]:
    with camara.ativa(), Execucao(fabrica, "camara-votacoes", {"teste": True}) as ex:
        ctx = ContextoJob(cfg, fabrica, ex)
        try:
            ok = JobCamaraVotacoes(ctx).processar_fatia(date(2026, 10, 14), date(2026, 10, 28))
        finally:
            ctx.fechar()
    return ok, ex
