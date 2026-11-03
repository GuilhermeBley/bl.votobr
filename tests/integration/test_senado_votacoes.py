"""Job senado-votacoes contra Postgres real e API do Senado simulada (critérios de T-203).

Só há uma fixture real de `/senador/{codigo}`; os demais senadores são sintetizados a partir
dela com nome, UF e sexo do próprio voto.
"""

import copy
import re
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.camara_falsa import rodar_seed, settings_teste
from tests.conftest import carregar_fixture
from votosbr.db.models import Pessoa, Proposicao, Votacao, VotacaoProposicao, Voto
from votosbr.domain.enums import Casa, VotacaoModalidade
from votosbr.etl.controle import Execucao
from votosbr.etl.jobs.contexto import ContextoJob
from votosbr.etl.jobs.senado_votacoes import JOB, JobSenadoVotacoes
from votosbr.sources.senado.client import BASE_URL

pytestmark = pytest.mark.integration

LISTAGEM = carregar_fixture("senado/votacoes/plenario_20260901_20261031.json")
TABELAS = (Votacao, Voto, Pessoa, Proposicao, VotacaoProposicao)


def _senador(request: httpx.Request, codigo: str) -> httpx.Response:
    voto = next(v for x in LISTAGEM for v in x["votos"] if str(v["codigoParlamentar"]) == codigo)
    corpo: dict[str, Any] = copy.deepcopy(carregar_fixture("senado/senador/5672.json"))
    ident = corpo["DetalheParlamentar"]["Parlamentar"]["IdentificacaoParlamentar"]
    ident.update(
        CodigoParlamentar=codigo,
        NomeParlamentar=voto["nomeParlamentar"],
        NomeCompletoParlamentar=voto["nomeParlamentar"],
        UfParlamentar=voto["siglaUFParlamentar"],
    )
    return httpx.Response(200, json=corpo)


def _rodar(fabrica: sessionmaker[Session], tmp_path: Path) -> tuple[bool, Execucao]:
    cfg = settings_teste(tmp_path).model_copy(update={"http_max_rps_senado": 0})
    base = re.escape(BASE_URL)
    with respx.mock(assert_all_called=False) as router, Execucao(fabrica, JOB, {}) as ex:
        router.get(url__regex=rf"{base}/votacao\?").mock(
            return_value=httpx.Response(200, json=LISTAGEM)
        )
        router.get(url__regex=rf"{base}/senador/(?P<codigo>\d+)$").mock(side_effect=_senador)
        ctx = ContextoJob(cfg, fabrica, ex)
        try:
            ok = JobSenadoVotacoes(ctx).processar_fatia(date(2026, 9, 1), date(2026, 10, 31))
        finally:
            ctx.fechar()
    return ok, ex


def _contagens(fabrica: sessionmaker[Session]) -> dict[str, int]:
    with fabrica() as s:
        return {
            m.__tablename__: s.scalar(select(func.count()).select_from(m)) or 0 for m in TABELAS
        }


def test_carga_completa_e_idempotente(fabrica: sessionmaker[Session], tmp_path: Path) -> None:
    rodar_seed(fabrica, settings_teste(tmp_path))

    ok, ex = _rodar(fabrica, tmp_path)
    assert ok and not ex.teve_erro
    primeira = _contagens(fabrica)
    assert primeira == {
        "votacao": 5,
        "voto": 405,
        "pessoa": 85,
        "proposicao": 4,  # PEC 221/2019 tem duas votações (1º e 2º turnos)
        "votacao_proposicao": 5,
    }

    ok, _ = _rodar(fabrica, tmp_path)
    assert ok and _contagens(fabrica) == primeira


def test_partidos_resolvidos_e_secreta(fabrica: sessionmaker[Session], tmp_path: Path) -> None:
    rodar_seed(fabrica, settings_teste(tmp_path))
    ok, ex = _rodar(fabrica, tmp_path)
    assert ok and not ex.teve_erro

    with fabrica() as s:
        # Toda sigla do Senado tem alias; "S/Partido" fica sem partido e sem sigla.
        sem_partido = s.scalars(select(Voto).where(Voto.partido_id.is_(None))).all()
        assert len(sem_partido) == 3
        assert all(v.partido_sigla_fonte is None for v in sem_partido)

        secreta = s.scalars(select(Votacao).where(Votacao.id_externo == "7104")).one()
        assert secreta.casa == Casa.SENADO
        assert secreta.modalidade == VotacaoModalidade.SECRETA
