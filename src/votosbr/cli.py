"""CLI `votosbr` (seção 6.4). Cada comando cria uma linha em `execucao_ingestao`."""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Any

import structlog
import typer

from votosbr.config import get_settings
from votosbr.db.session import engine_escrita, fabrica_sessao
from votosbr.domain.tempo import proxima_execucao
from votosbr.etl.controle import Execucao, SqlCheckpointRepo
from votosbr.etl.jobs import camara_deputados, seed
from votosbr.etl.jobs.base import PlanoJanela, executar_incremental, fatiar, planejar_janela
from votosbr.etl.jobs.camara_votacoes import JOB as JOB_CAMARA_VOTACOES
from votosbr.etl.jobs.camara_votacoes import JobCamaraVotacoes
from votosbr.etl.jobs.contexto import ContextoJob
from votosbr.etl.jobs.senado_votacoes import JOB as JOB_SENADO_VOTACOES
from votosbr.etl.jobs.senado_votacoes import JobSenadoVotacoes
from votosbr.logs import configurar_logs

log = structlog.get_logger(__name__)

app = typer.Typer(help="VotosBR: ingestão e manutenção dos dados.", no_args_is_help=True)
ingest = typer.Typer(help="Coleta de dados das fontes.", no_args_is_help=True)
checkpoint = typer.Typer(help="Checkpoints dos jobs incrementais.", no_args_is_help=True)
run = typer.Typer(help="Orquestração.", no_args_is_help=True)
app.add_typer(ingest, name="ingest")
app.add_typer(checkpoint, name="checkpoint")
app.add_typer(run, name="run")

DRY_RUN = typer.Option(False, "--dry-run", help="Mostra o que seria feito, sem buscar nada.")


@app.callback()
def _inicio() -> None:
    cfg = get_settings()
    configurar_logs(json=cfg.log_json, nivel=cfg.log_nivel)


@contextmanager
def _contexto(job: str, parametros: dict[str, Any]) -> Iterator[ContextoJob]:
    fabrica = fabrica_sessao(engine_escrita())
    with Execucao(fabrica, job, parametros) as execucao:
        ctx = ContextoJob(get_settings(), fabrica, execucao)
        try:
            yield ctx
        finally:
            ctx.fechar()


def _mostrar_plano(job: str, plano: PlanoJanela, checkpoint_atual: date | None) -> None:
    typer.echo(f"{job}: checkpoint={checkpoint_atual or '-'} intervalo={plano.desde}..{plano.ate}")
    typer.echo(f"  1. prioritária {plano.prioritaria[0]}..{plano.prioritaria[1]}")
    for i, (inicio, fim) in enumerate(plano.anteriores, start=2):
        typer.echo(f"  {i}. {inicio}..{fim}")


def _incremental_ou_manual(
    job: str,
    criar_processador: Callable[[ContextoJob], Callable[[date, date], bool]],
    desde: date | None,
    ate: date | None,
    dry_run: bool,
) -> bool:
    cfg = get_settings()
    if (desde is None) != (ate is None):
        raise typer.BadParameter("Use --desde e --ate juntos.")

    if desde is not None and ate is not None:  # manual: nunca move o checkpoint
        fatias = list(fatiar(desde, ate, cfg.tamanho_fatia_dias))
        if dry_run:
            typer.echo(f"{job} (manual, não move checkpoint): {desde}..{ate}")
            for i, (inicio, fim) in enumerate(fatias, start=1):
                typer.echo(f"  {i}. {inicio}..{fim}")
            return True
        with _contexto(job, {"desde": desde, "ate": ate, "modo": "manual"}) as ctx:
            processar = criar_processador(ctx)
            resultados = [processar(inicio, fim) for inicio, fim in fatias]
            return all(resultados)

    checkpoints = SqlCheckpointRepo(fabrica_sessao(engine_escrita()))
    atual = checkpoints.obter(job)
    plano = planejar_janela(datetime.now(UTC), atual, cfg)
    if dry_run:
        _mostrar_plano(job, plano, atual)
        return True
    with _contexto(job, {"modo": "incremental", "desde": plano.desde, "ate": plano.ate}) as ctx:
        return executar_incremental(
            job, plano, criar_processador(ctx), ctx.checkpoints, ctx.execucao.id
        )


def _pendente(tarefa: str) -> None:
    typer.echo(f"Ainda não implementado ({tarefa}).", err=True)
    raise typer.Exit(code=2)


# --- seed -------------------------------------------------------------------------------------


@app.command("seed")
def cmd_seed() -> None:
    """Legislaturas, partidos e temas (idempotente)."""
    with _contexto(seed.JOB, {}) as ctx:
        seed.executar(ctx)


# --- ingest -----------------------------------------------------------------------------------


@ingest.command("camara-votacoes")
def cmd_camara_votacoes(
    desde: datetime | None = typer.Option(None, formats=["%Y-%m-%d"]),
    ate: datetime | None = typer.Option(None, formats=["%Y-%m-%d"]),
    ano: int | None = typer.Option(None, help="Backfill por ano (com --modo bulk)."),
    modo: str = typer.Option("api", help="api | bulk"),
    dry_run: bool = DRY_RUN,
) -> None:
    """Incremental via API com checkpoint; --desde/--ate para execução manual."""
    if modo == "bulk" or ano is not None:
        _pendente("T-104: backfill via arquivos em massa")
    ok = _incremental_ou_manual(
        JOB_CAMARA_VOTACOES,
        lambda ctx: JobCamaraVotacoes(ctx).processar_fatia,
        desde.date() if desde else None,
        ate.date() if ate else None,
        dry_run,
    )
    if not ok:
        raise typer.Exit(code=1)


@ingest.command("camara-deputados")
def cmd_camara_deputados(legislatura: int = typer.Option(...), dry_run: bool = DRY_RUN) -> None:
    """Deputados de uma legislatura inteira."""
    if dry_run:
        typer.echo(f"{camara_deputados.JOB}: legislatura {legislatura}")
        return
    with _contexto(camara_deputados.JOB, {"legislatura": legislatura}) as ctx:
        camara_deputados.executar(ctx, legislatura)


@ingest.command("senado-senadores")
def cmd_senado_senadores(legislatura: int = typer.Option(...)) -> None:
    """Senadores de uma legislatura."""
    _pendente("T-202")


@ingest.command("senado-votacoes")
def cmd_senado_votacoes(
    desde: datetime | None = typer.Option(None, formats=["%Y-%m-%d"]),
    ate: datetime | None = typer.Option(None, formats=["%Y-%m-%d"]),
    dry_run: bool = DRY_RUN,
) -> None:
    """Incremental de votações do Senado com checkpoint; --desde/--ate para execução manual."""
    ok = _incremental_ou_manual(
        JOB_SENADO_VOTACOES,
        lambda ctx: JobSenadoVotacoes(ctx).processar_fatia,
        desde.date() if desde else None,
        ate.date() if ate else None,
        dry_run,
    )
    if not ok:
        raise typer.Exit(code=1)


# --- checkpoint -------------------------------------------------------------------------------


@checkpoint.command("mostrar")
def cmd_checkpoint_mostrar() -> None:
    """Estado de todos os jobs incrementais."""
    for c in SqlCheckpointRepo(fabrica_sessao(engine_escrita())).todos():
        typer.echo(f"{c.job}\t{c.processado_ate}\texecucao={c.execucao_id}\t{c.atualizado_em}")


@checkpoint.command("definir")
def cmd_checkpoint_definir(
    job: str, data: datetime = typer.Argument(..., formats=["%Y-%m-%d"])
) -> None:
    """Ajuste manual (pode recuar), registrado em execucao_ingestao."""
    with _contexto("checkpoint-definir", {"job": job, "data": data.date()}) as ctx:
        ctx.checkpoints.definir(job, data.date(), ctx.execucao.id)


# --- run --------------------------------------------------------------------------------------


@run.command("diario")
def cmd_run_diario() -> None:
    """Incremental completo (seção 6.3). Etapas ainda não implementadas são puladas com aviso."""
    if not _executar_diario():
        raise typer.Exit(code=1)


@run.command("agendado")
def cmd_run_agendado(
    hora: int = typer.Option(6, min=0, max=23, help="Hora (Brasília) da execução diária."),
    ao_iniciar: bool = typer.Option(True, help="Executa uma vez assim que o processo sobe."),
) -> None:
    """Processo contínuo: `run diario` todo dia na hora indicada (worker do Docker Compose)."""
    if ao_iniciar:
        _executar_diario_protegido()
    while True:
        alvo = proxima_execucao(datetime.now(UTC), hora)
        log.info("agendado.aguardando", proxima=alvo.isoformat())
        time.sleep(max(0.0, (alvo - datetime.now(UTC)).total_seconds()))
        _executar_diario_protegido()


def _executar_diario_protegido() -> None:
    """Uma falha não derruba o agendador; o histórico fica em `execucao_ingestao`."""
    try:
        ok = _executar_diario()
    except Exception:
        log.exception("agendado.erro")
    else:
        log.info("agendado.concluido", sucesso=ok)


def _executar_diario() -> bool:
    # Uma fonte fora do ar não impede a outra; o resultado combina as duas.
    ok_camara = _incremental_ou_manual(
        JOB_CAMARA_VOTACOES, lambda ctx: JobCamaraVotacoes(ctx).processar_fatia, None, None, False
    )
    ok_senado = _incremental_ou_manual(
        JOB_SENADO_VOTACOES, lambda ctx: JobSenadoVotacoes(ctx).processar_fatia, None, None, False
    )
    for etapa in (
        "classify votacoes (T-303)",
        "derive nao-registrou (T-107)",
        "check qualidade (T-305)",
        "refresh views (T-403)",
    ):
        typer.echo(f"pulado: {etapa}", err=True)
    return ok_camara and ok_senado


# --- etapas futuras ---------------------------------------------------------------------------


@app.command("resolve")
def cmd_resolve(alvo: str = typer.Argument(..., help="pessoas | processos")) -> None:
    _pendente("T-205 / T-301")


@app.command("classify")
def cmd_classify(alvo: str = typer.Argument(..., help="votacoes")) -> None:
    _pendente("T-303")


@app.command("derive")
def cmd_derive(alvo: str = typer.Argument(..., help="nao-registrou")) -> None:
    _pendente("T-107")


@app.command("check")
def cmd_check(alvo: str = typer.Argument(..., help="qualidade")) -> None:
    _pendente("T-305")


@app.command("refresh")
def cmd_refresh(alvo: str = typer.Argument(..., help="views")) -> None:
    _pendente("T-403")


@app.command("reprocess")
def cmd_reprocess(
    fonte: str = typer.Option(...),
    desde: datetime = typer.Option(..., formats=["%Y-%m-%d"]),
) -> None:
    """Reconstrói o core a partir do RawStore, sem rede."""
    _pendente("reprocessamento a partir do raw")


if __name__ == "__main__":
    app()
