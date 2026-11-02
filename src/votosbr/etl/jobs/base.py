"""Janela de consulta e checkpoint dos jobs incrementais de votações (seção 6.2.1).

`planejar_janela` é pura (recebe `agora` e o checkpoint): testável sem banco e sem relógio real.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

from votosbr.config import Settings
from votosbr.domain.tempo import TZ_BRASILIA


@dataclass(frozen=True)
class PlanoJanela:
    desde: date
    ate: date
    prioritaria: tuple[date, date]  # [ontem, hoje], processada primeiro
    anteriores: list[tuple[date, date]]  # revisão e atraso, em ordem cronológica


class CheckpointRepo(Protocol):
    def obter(self, job: str) -> date | None: ...

    def avancar(self, job: str, data: date, execucao_id: int | None = None) -> None:
        """`max(atual, data)`: nunca recua."""
        ...


def fatiar(desde: date, ate: date, dias: int) -> Iterator[tuple[date, date]]:
    inicio = desde
    while inicio <= ate:
        fim = min(inicio + timedelta(days=dias - 1), ate)
        yield inicio, fim
        inicio = fim + timedelta(days=1)


def planejar_janela(agora: datetime, checkpoint: date | None, cfg: Settings) -> PlanoJanela:
    hoje = agora.astimezone(TZ_BRASILIA).date()
    ontem = hoje - timedelta(days=1)
    base = checkpoint or cfg.ingestao_data_inicial
    desde = max(
        cfg.ingestao_data_inicial,
        min(ontem, base - timedelta(days=cfg.janela_revisao_dias)),
    )
    inicio_prioritaria = max(desde, ontem)
    anteriores = list(fatiar(desde, inicio_prioritaria - timedelta(days=1), cfg.tamanho_fatia_dias))
    return PlanoJanela(desde, hoje, (inicio_prioritaria, hoje), anteriores)


def executar_incremental(
    job: str,
    plano: PlanoJanela,
    processar_fatia: Callable[[date, date], bool],
    checkpoints: CheckpointRepo,
    execucao_id: int | None = None,
) -> bool:
    """Processa `[ontem, hoje]` primeiro e depois as fatias anteriores em ordem cronológica.

    `processar_fatia` devolve False quando algum registro da fatia falhou. O checkpoint só
    avança enquanto as fatias anteriores forem concluídas sem falha (contiguidade), e só chega
    a `plano.ate` se tudo, inclusive a fatia prioritária, tiver dado certo. Todas as fatias são
    processadas mesmo após uma falha (tolerância a falhas parciais).
    """
    prioritaria_ok = processar_fatia(*plano.prioritaria)  # dados mais recentes primeiro
    contiguo = True
    for inicio, fim in plano.anteriores:
        contiguo = processar_fatia(inicio, fim) and contiguo
        if contiguo:
            checkpoints.avancar(job, fim, execucao_id)
    tudo_ok = contiguo and prioritaria_ok
    if tudo_ok:
        checkpoints.avancar(job, plano.ate, execucao_id)  # só depois de tudo concluído
    return tudo_ok
