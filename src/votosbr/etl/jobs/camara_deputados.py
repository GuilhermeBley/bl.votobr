"""Job `camara-deputados`: pessoas de uma legislatura inteira (T-102, parcial).

Implementado: pessoa + identificador externo a partir de `/deputados/{id}`.
Pendente (T-102): mandato, exercício e filiação a partir de `/deputados/{id}/historico`.
"""

from votosbr.domain.enums import FonteDado
from votosbr.etl import loaders
from votosbr.etl.jobs.contexto import ContextoJob
from votosbr.etl.mappers import camara as mapper

JOB = "camara-deputados"


def executar(ctx: ContextoJob, legislatura: int) -> None:
    for resumo in ctx.camara.deputados(legislatura):
        ctx.execucao.lidos += 1
        try:
            detalhe, _ = ctx.camara.deputado(resumo.id)
            with ctx.fabrica() as s, s.begin():
                loaders.upsert_pessoa(
                    s, mapper.mapear_pessoa(detalhe), FonteDado.CAMARA, str(resumo.id)
                )
            ctx.execucao.gravados += 1
        except Exception as exc:  # tolerância a falhas parciais
            ctx.execucao.erro("deputado.falhou", id_externo=resumo.id, erro=repr(exc))
