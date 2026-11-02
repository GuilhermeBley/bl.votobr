"""Job `camara-votacoes`: incremental de votações de Plenário via API, com checkpoint (T-103).

Para cada votação: detalhe + votos + orientações -> mapper puro -> upserts numa transação
própria. Parlamentar desconhecido é buscado sob demanda (`/deputados/{id}`). Falha numa votação
é registrada e a carga continua; a fatia fica marcada como incompleta e segura o checkpoint.
"""

from datetime import date

import structlog
from sqlalchemy.orm import Session

from votosbr.domain.enums import BancadaTipo, FonteDado
from votosbr.etl import loaders
from votosbr.etl.jobs.contexto import ContextoJob
from votosbr.etl.mappers import camara as mapper
from votosbr.etl.mappers.tipos import PessoaCore, VotacaoMapeada
from votosbr.sources.camara.schemas import VotacaoResumo
from votosbr.sources.http import ErroFonte

JOB = "camara-votacoes"
FONTE = FonteDado.CAMARA

log = structlog.get_logger(__name__)


class JobCamaraVotacoes:
    def __init__(self, ctx: ContextoJob) -> None:
        self.ctx = ctx
        self._pessoas: dict[str, int] = {}  # cache id do deputado -> pessoa_id

    def processar_fatia(self, inicio: date, fim: date) -> bool:
        log.info("fatia.inicio", inicio=inicio.isoformat(), fim=fim.isoformat())
        try:
            resumos = list(self.ctx.camara.votacoes(inicio, fim))
        except ErroFonte as exc:
            self.ctx.execucao.erro("fatia.listagem_falhou", inicio=inicio, fim=fim, erro=str(exc))
            return False

        ok = True
        for resumo, _raw_lista in resumos:
            self.ctx.execucao.lidos += 1
            try:
                self.processar_votacao(resumo)
                self.ctx.execucao.gravados += 1
            except Exception as exc:  # tolerância a falhas parciais (seção 0.2.5)
                ok = False
                self.ctx.execucao.erro("votacao.falhou", id_externo=resumo.id, erro=repr(exc))
        log.info("fatia.fim", inicio=inicio.isoformat(), fim=fim.isoformat(), votacoes=len(resumos))
        return ok

    def processar_votacao(self, resumo: VotacaoResumo) -> None:
        # Toda a rede antes da transação: nada de conexão aberta esperando HTTP.
        camara = self.ctx.camara
        detalhe, raw_id = camara.votacao(resumo.id)
        mapeada = mapper.mapear_votacao(
            resumo,
            detalhe,
            camara.votos(resumo.id),
            camara.orientacoes(resumo.id),
            self.ctx.normalizador,
            self.ctx.classificador,
        )
        novas_pessoas = self._buscar_pessoas_desconhecidas(mapeada)

        with self.ctx.fabrica() as s, s.begin():
            criadas = {
                id_ext: loaders.upsert_pessoa(s, p, FONTE, id_ext)
                for id_ext, p in novas_pessoas.items()
            }
            self._gravar(s, mapeada, raw_id, {**self._pessoas, **criadas})
        self._pessoas.update(criadas)  # só após o commit

    def _buscar_pessoas_desconhecidas(self, mapeada: VotacaoMapeada) -> dict[str, PessoaCore]:
        ids = {v.id_externo_pessoa for v in mapeada.votos} - self._pessoas.keys()
        if not ids:
            return {}
        with self.ctx.fabrica() as s:
            self._pessoas.update(loaders.pessoas_por_id_externo(s, FONTE, sorted(ids)))
        faltantes = ids - self._pessoas.keys()
        novas: dict[str, PessoaCore] = {}
        for id_ext in sorted(faltantes):
            deputado, _ = self.ctx.camara.deputado(int(id_ext))
            novas[id_ext] = mapper.mapear_pessoa(deputado)
            log.info("pessoa.sob_demanda", id_externo=id_ext)
        return novas

    def _gravar(
        self, s: Session, m: VotacaoMapeada, raw_id: int | None, pessoas: dict[str, int]
    ) -> None:
        v = m.votacao
        votacao_id = loaders.upsert_votacao(s, v, raw_id)

        for proposicao, papel in m.proposicoes:
            proposicao_id = loaders.upsert_proposicao(s, proposicao, raw_id)
            loaders.ligar_votacao_proposicao(s, votacao_id, proposicao_id, papel)

        for o in m.orientacoes:
            partido_id = (
                loaders.resolver_partido(s, FONTE, o.bancada_sigla, v.data)
                if o.bancada_tipo == BancadaTipo.PARTIDO
                else None
            )
            bancada_id = loaders.obter_ou_criar_bancada(
                s, v.casa, o.bancada_sigla, o.bancada_tipo, partido_id
            )
            loaders.upsert_orientacao(
                s, votacao_id, bancada_id, o.orientacao, o.orientacao_original
            )

        siglas_nao_resolvidas: set[str] = set()
        for voto in m.votos:
            partido_id = loaders.resolver_partido(s, FONTE, voto.partido_sigla_fonte, v.data)
            if partido_id is None and voto.partido_sigla_fonte:
                siglas_nao_resolvidas.add(voto.partido_sigla_fonte)
            loaders.upsert_voto(s, votacao_id, pessoas[voto.id_externo_pessoa], voto, partido_id)
        if siglas_nao_resolvidas:  # C04
            self.ctx.execucao.alerta(
                "partido.sigla_nao_resolvida",
                votacao=v.id_publico,
                siglas=sorted(siglas_nao_resolvidas),
            )

        for nm in m.nao_mapeados:  # C05
            loaders.registrar_nao_mapeado(s, FONTE, nm.campo, nm.valor, nm.exemplo_ref)
            self.ctx.execucao.alerta(
                "valor_nao_mapeado", campo=nm.campo, valor=nm.valor, ref=nm.exemplo_ref
            )
