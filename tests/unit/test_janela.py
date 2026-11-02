"""Tabela de exemplos da seção 6.2.1 + fuso + ordem de processamento + checkpoint."""

import itertools
from datetime import UTC, date, datetime, timedelta

import pytest

from votosbr.config import Settings
from votosbr.domain.tempo import TZ_BRASILIA
from votosbr.etl.jobs.base import executar_incremental, fatiar, planejar_janela


def cfg(janela: int = 7, fatia: int = 7) -> Settings:
    return Settings(
        ingestao_data_inicial=date(2026, 11, 1),
        janela_revisao_dias=janela,
        tamanho_fatia_dias=fatia,
    )


def meio_dia_brasilia(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 12, tzinfo=TZ_BRASILIA)


@pytest.mark.parametrize(
    ("hoje", "checkpoint", "janela", "desde", "ate"),
    [
        (date(2026, 11, 1), None, 7, date(2026, 11, 1), date(2026, 11, 1)),
        (date(2026, 11, 2), date(2026, 11, 1), 7, date(2026, 11, 1), date(2026, 11, 2)),
        (date(2026, 11, 20), date(2026, 11, 19), 7, date(2026, 11, 12), date(2026, 11, 20)),
        (date(2026, 12, 10), date(2026, 11, 19), 7, date(2026, 11, 12), date(2026, 12, 10)),
        (date(2026, 11, 20), date(2026, 11, 19), 0, date(2026, 11, 19), date(2026, 11, 20)),
        (date(2026, 11, 20), date(2026, 11, 20), 0, date(2026, 11, 19), date(2026, 11, 20)),
    ],
)
def test_exemplos_da_secao_6_2_1(
    hoje: date, checkpoint: date | None, janela: int, desde: date, ate: date
) -> None:
    plano = planejar_janela(meio_dia_brasilia(hoje), checkpoint, cfg(janela))
    assert (plano.desde, plano.ate) == (desde, ate)
    # [ontem, hoje] sempre coberto, salvo antes da data inicial
    assert plano.prioritaria == (max(desde, hoje - timedelta(days=1)), hoje)


def test_primeira_execucao_nao_consulta_antes_da_data_inicial() -> None:
    plano = planejar_janela(meio_dia_brasilia(date(2026, 11, 1)), None, cfg())
    assert plano.prioritaria == (date(2026, 11, 1), date(2026, 11, 1))
    assert plano.anteriores == []


def test_hoje_e_a_data_de_brasilia_nao_a_utc() -> None:
    # 2026-11-21 01:00 UTC = 2026-11-20 22:00 em Brasília
    agora = datetime(2026, 11, 21, 1, 0, tzinfo=UTC)
    plano = planejar_janela(agora, date(2026, 11, 19), cfg())
    assert plano.ate == date(2026, 11, 20)
    assert plano.prioritaria == (date(2026, 11, 19), date(2026, 11, 20))


def test_job_parado_tres_semanas_fatia_em_ordem_cronologica() -> None:
    plano = planejar_janela(meio_dia_brasilia(date(2026, 12, 10)), date(2026, 11, 19), cfg())
    assert plano.prioritaria == (date(2026, 12, 9), date(2026, 12, 10))
    assert plano.anteriores == [
        (date(2026, 11, 12), date(2026, 11, 18)),
        (date(2026, 11, 19), date(2026, 11, 25)),
        (date(2026, 11, 26), date(2026, 12, 2)),
        (date(2026, 12, 3), date(2026, 12, 8)),
    ]


def test_fatiar_cobre_intervalo_sem_buracos() -> None:
    fatias = list(fatiar(date(2026, 11, 1), date(2026, 11, 10), 3))
    assert fatias[0][0] == date(2026, 11, 1)
    assert fatias[-1][1] == date(2026, 11, 10)
    for (_, fim), (inicio, _) in itertools.pairwise(fatias):
        assert inicio == fim + timedelta(days=1)


class CheckpointsFalsos:
    def __init__(self, inicial: date | None = None) -> None:
        self.valor = inicial
        self.chamadas: list[date] = []

    def obter(self, job: str) -> date | None:
        return self.valor

    def avancar(self, job: str, data: date, execucao_id: int | None = None) -> None:
        self.chamadas.append(data)
        self.valor = max(self.valor, data) if self.valor else data


def test_recente_primeiro_e_checkpoint_avanca_contiguo() -> None:
    plano = planejar_janela(meio_dia_brasilia(date(2026, 12, 10)), date(2026, 11, 19), cfg())
    ordem: list[tuple[date, date]] = []
    cps = CheckpointsFalsos(date(2026, 11, 19))

    def processar(inicio: date, fim: date) -> bool:
        ordem.append((inicio, fim))
        return True

    assert executar_incremental("job", plano, processar, cps)
    assert ordem[0] == plano.prioritaria
    assert ordem[1:] == plano.anteriores
    assert cps.valor == date(2026, 12, 10)


def test_falha_numa_fatia_segura_o_checkpoint_mas_processa_as_demais() -> None:
    plano = planejar_janela(meio_dia_brasilia(date(2026, 12, 10)), date(2026, 11, 19), cfg())
    processadas: list[tuple[date, date]] = []
    cps = CheckpointsFalsos(date(2026, 11, 19))
    fatia_ruim = plano.anteriores[1]  # 19/11..25/11

    def processar(inicio: date, fim: date) -> bool:
        processadas.append((inicio, fim))
        return (inicio, fim) != fatia_ruim

    assert not executar_incremental("job", plano, processar, cps)
    assert len(processadas) == 1 + len(plano.anteriores)
    assert cps.valor == date(2026, 11, 19)  # 18/11 < checkpoint atual: nunca recua


def test_falha_na_prioritaria_nao_leva_checkpoint_ate_hoje() -> None:
    plano = planejar_janela(meio_dia_brasilia(date(2026, 11, 20)), date(2026, 11, 19), cfg())
    cps = CheckpointsFalsos(date(2026, 11, 19))

    def processar(inicio: date, fim: date) -> bool:
        return (inicio, fim) != plano.prioritaria

    assert not executar_incremental("job", plano, processar, cps)
    assert cps.valor == date(2026, 11, 19)
