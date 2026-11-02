from fastapi import APIRouter
from sqlalchemy import func, select

from votosbr.api.deps import SessaoDep, SettingsDep
from votosbr.api.schemas.comum import Envelope
from votosbr.api.schemas.referencia import AtualizacaoFonte, ValorEnum
from votosbr.db.models import CheckpointIngestao, ExecucaoIngestao
from votosbr.domain.enums import (
    BancadaTipo,
    Casa,
    OrientacaoTipo,
    StatusExecucao,
    VotacaoModalidade,
    VotacaoObjeto,
    VotoTipo,
)
from votosbr.domain.rotulos import ROTULOS

router = APIRouter(prefix="/meta", tags=["meta"])

_ENUMS_PUBLICOS = {
    "casa": Casa,
    "voto": VotoTipo,
    "orientacao": OrientacaoTipo,
    "modalidade": VotacaoModalidade,
    "objeto": VotacaoObjeto,
    "bancada_tipo": BancadaTipo,
}


@router.get("/enums", response_model=Envelope[dict[str, list[ValorEnum]]])
def enums() -> Envelope[dict[str, list[ValorEnum]]]:
    """Rótulos em português de todos os enums do contrato."""
    return Envelope(
        data={
            nome: [ValorEnum(valor=m.value, rotulo=ROTULOS[enum][m.value]) for m in enum]
            for nome, enum in _ENUMS_PUBLICOS.items()
        }
    )


@router.get("/atualizacao", response_model=Envelope[list[AtualizacaoFonte]])
def atualizacao(sessao: SessaoDep, settings: SettingsDep) -> Envelope[list[AtualizacaoFonte]]:
    """Por job incremental: última execução bem-sucedida e até quando há dados (checkpoint)."""
    ultima = (
        select(ExecucaoIngestao.job, func.max(ExecucaoIngestao.fim).label("fim"))
        .where(
            ExecucaoIngestao.status.in_(
                [StatusExecucao.SUCESSO.value, StatusExecucao.SUCESSO_COM_ALERTAS.value]
            )
        )
        .group_by(ExecucaoIngestao.job)
        .subquery()
    )
    linhas = sessao.execute(
        select(CheckpointIngestao.job, CheckpointIngestao.processado_ate, ultima.c.fim)
        .outerjoin(ultima, ultima.c.job == CheckpointIngestao.job)
        .order_by(CheckpointIngestao.job)
    )
    return Envelope(
        data=[
            AtualizacaoFonte(
                job=job,
                fonte=job.split("-", 1)[0].upper(),
                ultima_execucao_sucesso=fim,
                dados_ate=processado_ate,
                dados_desde=settings.ingestao_data_inicial,
            )
            for job, processado_ate, fim in linhas
        ]
    )
