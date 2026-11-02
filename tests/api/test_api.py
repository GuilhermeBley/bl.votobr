"""Contrato da API: envelope, problem details e votações sobre dados carregados pelo job."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.camara_falsa import (
    ID_NOMINAL,
    ID_SIMBOLICA,
    CamaraFalsa,
    rodar_fatia,
    rodar_seed,
    settings_teste,
)
from votosbr.api.deps import get_sessao
from votosbr.api.main import create_app


@pytest.fixture
def cliente_sem_banco() -> TestClient:
    return TestClient(create_app())


def test_openapi_publicado_em_v1(cliente_sem_banco: TestClient) -> None:
    r = cliente_sem_banco.get("/api/v1/openapi.json")
    assert r.status_code == 200
    caminhos = r.json()["paths"]
    assert "/api/v1/votacoes/{id_publico}/votos" in caminhos


def test_meta_enums_com_rotulos(cliente_sem_banco: TestClient) -> None:
    corpo = cliente_sem_banco.get("/api/v1/meta/enums").json()
    voto = {i["valor"]: i["rotulo"] for i in corpo["data"]["voto"]}
    assert voto["NAO_REGISTROU"] == "Não registrou voto"
    assert "gerado_em" in corpo["meta"] and corpo["meta"]["gerado_em"].endswith("Z")


def test_rota_inexistente_em_problem_details(cliente_sem_banco: TestClient) -> None:
    r = cliente_sem_banco.get("/api/v1/nao-existe")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["status"] == 404


def test_validacao_em_problem_details(cliente_sem_banco: TestClient) -> None:
    r = cliente_sem_banco.get("/api/v1/votacoes", params={"por_pagina": 1000})
    assert r.status_code == 422
    assert r.json()["errors"]


@pytest.fixture
def cliente(fabrica: sessionmaker[Session], tmp_path: Path) -> Iterator[TestClient]:
    cfg = settings_teste(tmp_path)
    rodar_seed(fabrica, cfg)
    rodar_fatia(fabrica, cfg, CamaraFalsa())
    app = create_app()

    def sessao() -> Iterator[Session]:
        with fabrica() as s:
            yield s

    app.dependency_overrides[get_sessao] = sessao
    yield TestClient(app)


@pytest.mark.integration
def test_listar_votacoes(cliente: TestClient) -> None:
    corpo = cliente.get("/api/v1/votacoes").json()
    assert corpo["meta"]["paginacao"]["total"] == 2
    assert corpo["data"][0]["id"] == f"camara-{ID_SIMBOLICA}"  # mais recente primeiro


@pytest.mark.integration
def test_detalhe_votacao_nominal(cliente: TestClient) -> None:
    d = cliente.get(f"/api/v1/votacoes/camara-{ID_NOMINAL}").json()["data"]
    assert d["placar"] == {"SIM": 461, "NAO": 4, "PRESIDENTE": 1}
    assert d["modalidade"] == "NOMINAL"
    assert d["data_hora"] == "2026-10-14T22:42:50Z"  # 19:42:50 em Brasília
    assert sum(sum(p["contagem"].values()) for p in d["placar_por_partido"]) == 466
    governo = next(o for o in d["orientacoes"] if o["tipo"] == "GOVERNO")
    assert governo["orientacao"] == "SIM"
    assert d["fontes"][0]["url"].endswith(ID_NOMINAL)


@pytest.mark.integration
def test_detalhe_simbolica_traz_aviso(cliente: TestClient) -> None:
    d = cliente.get(f"/api/v1/votacoes/camara-{ID_SIMBOLICA}").json()["data"]
    assert [a["codigo"] for a in d["avisos"]] == ["VOTACAO_SIMBOLICA"]
    assert d["placar"] == {}


@pytest.mark.integration
def test_votos_filtrados_e_csv(cliente: TestClient) -> None:
    r = cliente.get(f"/api/v1/votacoes/camara-{ID_NOMINAL}/votos", params={"uf": "AL"})
    corpo = r.json()
    assert corpo["data"] and all(v["uf"] == "AL" for v in corpo["data"])
    pl = cliente.get(
        f"/api/v1/votacoes/camara-{ID_NOMINAL}/votos", params={"partido": "pl"}
    ).json()["data"]
    assert pl and all(v["orientacao_partido"] == "SIM" for v in pl)
    assert all(v["seguiu_orientacao_partido"] == (v["voto"] == "SIM") for v in pl)

    csv = cliente.get(f"/api/v1/votacoes/camara-{ID_NOMINAL}/votos", params={"formato": "csv"})
    assert csv.headers["content-type"].startswith("text/csv")
    assert len(csv.text.strip().splitlines()) == 467


@pytest.mark.integration
def test_votacao_inexistente(cliente: TestClient) -> None:
    r = cliente.get("/api/v1/votacoes/camara-0-0")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")


@pytest.mark.integration
def test_referencias(cliente: TestClient) -> None:
    assert len(cliente.get("/api/v1/legislaturas").json()["data"]) == 4
    assert any(p["slug"] == "pt" for p in cliente.get("/api/v1/partidos").json()["data"])
