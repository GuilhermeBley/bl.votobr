"""Job camara-votacoes contra Postgres real e API da Câmara simulada (critérios de T-103)."""

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.camara_falsa import (
    ID_NOMINAL,
    CamaraFalsa,
    rodar_fatia,
    rodar_seed,
    settings_teste,
)
from votosbr.db.models import (
    CheckpointIngestao,
    ExecucaoIngestao,
    Orientacao,
    Pessoa,
    Proposicao,
    RawDocumento,
    ValorNaoMapeado,
    Votacao,
    VotacaoProposicao,
    Voto,
)
from votosbr.domain.enums import StatusExecucao, VotacaoModalidade, VotoTipo
from votosbr.etl.controle import SqlCheckpointRepo
from votosbr.etl.jobs.base import PlanoJanela, executar_incremental

pytestmark = pytest.mark.integration

TABELAS = (Votacao, Voto, Orientacao, Pessoa, Proposicao, VotacaoProposicao)


def contagens(fabrica: sessionmaker[Session]) -> dict[str, int]:
    with fabrica() as s:
        return {
            m.__tablename__: s.scalar(select(func.count()).select_from(m)) or 0 for m in TABELAS
        }


def test_carga_completa_e_idempotente(fabrica: sessionmaker[Session], tmp_path: Path) -> None:
    cfg = settings_teste(tmp_path)
    rodar_seed(fabrica, cfg)
    camara = CamaraFalsa()

    ok, ex = rodar_fatia(fabrica, cfg, camara)
    assert ok and not ex.teve_erro
    primeira = contagens(fabrica)
    assert primeira == {
        "votacao": 2,
        "voto": 466,
        "orientacao": 11,
        "pessoa": 466,
        "proposicao": 3,  # PLP 186/2026, PL 3099/2019, REQ 4194/2026
        "votacao_proposicao": 3,
    }

    ok, _ = rodar_fatia(fabrica, cfg, camara)
    assert ok
    assert contagens(fabrica) == primeira  # rodar duas vezes não altera contagens

    with fabrica() as s:
        nominal = s.scalar(select(Votacao).where(Votacao.id_publico == f"camara-{ID_NOMINAL}"))
        assert nominal is not None
        assert nominal.modalidade == VotacaoModalidade.NOMINAL
        assert (
            s.scalar(select(func.count()).select_from(Voto).where(Voto.partido_id.is_(None))) == 0
        )
        assert s.scalar(select(func.count()).select_from(ValorNaoMapeado)) == 0
        assert s.scalar(select(func.count()).select_from(RawDocumento)) > 0
        status = s.scalars(select(ExecucaoIngestao.status)).all()
        assert StatusExecucao.SUCESSO.value in status


def test_correcao_na_fonte_atualiza_voto(fabrica: sessionmaker[Session], tmp_path: Path) -> None:
    cfg = settings_teste(tmp_path)
    rodar_seed(fabrica, cfg)
    camara = CamaraFalsa()
    rodar_fatia(fabrica, cfg, camara)

    alvo = camara.votos_nominal["dados"][0]
    assert alvo["tipoVoto"] == "Sim"
    alvo["tipoVoto"] = "Não"  # correção publicada depois na fonte
    rodar_fatia(fabrica, cfg, camara)

    with fabrica() as s:
        votos = dict(s.execute(select(Voto.voto, func.count()).group_by(Voto.voto)).all())
    assert votos[VotoTipo.SIM] == 460
    assert votos[VotoTipo.NAO] == 5


def test_valor_desconhecido_registrado_sem_derrubar_carga(
    fabrica: sessionmaker[Session], tmp_path: Path
) -> None:
    cfg = settings_teste(tmp_path)
    rodar_seed(fabrica, cfg)
    camara = CamaraFalsa()
    camara.votos_nominal["dados"][0]["tipoVoto"] = "Voto Inédito"

    ok, ex = rodar_fatia(fabrica, cfg, camara)
    assert ok
    with fabrica() as s:
        registro = s.scalar(select(ValorNaoMapeado))
        assert registro is not None and registro.valor == "Voto Inédito"
        assert s.scalar(select(func.count()).where(Voto.voto == VotoTipo.OUTRO)) == 1
    assert any(o["tipo"] == "valor_nao_mapeado" for o in ex.ocorrencias)


def test_falha_numa_votacao_nao_perde_as_demais_e_segura_checkpoint(
    fabrica: sessionmaker[Session], tmp_path: Path
) -> None:
    cfg = settings_teste(tmp_path)
    rodar_seed(fabrica, cfg)
    camara = CamaraFalsa()
    camara.falhar_detalhe.add(ID_NOMINAL)
    checkpoints = SqlCheckpointRepo(fabrica)
    checkpoints.avancar("camara-votacoes", date(2026, 10, 1))

    from votosbr.etl.controle import Execucao
    from votosbr.etl.jobs.camara_votacoes import JobCamaraVotacoes
    from votosbr.etl.jobs.contexto import ContextoJob

    plano = PlanoJanela(
        desde=date(2026, 10, 2),
        ate=date(2026, 10, 28),
        prioritaria=(date(2026, 10, 27), date(2026, 10, 28)),
        anteriores=[(date(2026, 10, 2), date(2026, 10, 26))],
    )
    with camara.ativa(), Execucao(fabrica, "camara-votacoes", {}) as ex:
        ctx = ContextoJob(cfg, fabrica, ex)
        ok = executar_incremental(
            "camara-votacoes", plano, JobCamaraVotacoes(ctx).processar_fatia, checkpoints, ex.id
        )
        ctx.fechar()

    assert not ok
    assert contagens(fabrica)["votacao"] == 1  # a simbólica entrou
    assert checkpoints.obter("camara-votacoes") == date(2026, 10, 1)  # não avançou

    with fabrica() as s:
        execucao = s.scalars(
            select(ExecucaoIngestao).where(ExecucaoIngestao.job == "camara-votacoes")
        ).one()
        assert execucao.status == StatusExecucao.SUCESSO_COM_ALERTAS.value
        assert s.get(CheckpointIngestao, "camara-votacoes") is not None
