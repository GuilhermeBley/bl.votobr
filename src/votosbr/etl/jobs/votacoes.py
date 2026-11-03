"""Base dos jobs incrementais de votações de Plenário (Câmara e Senado).

Para cada votação da fatia: mapeamento puro -> pessoas desconhecidas buscadas sob demanda ->
upserts numa transação própria. Falha numa votação é registrada e a carga continua; a fatia fica
marcada como incompleta e segura o checkpoint (decisão 011). Cada fonte implementa a listagem,
o mapeamento e a busca de parlamentar.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import ClassVar

import structlog
from sqlalchemy.orm import Session

from votosbr.domain.enums import BancadaTipo, FonteDado
from votosbr.etl import loaders
from votosbr.etl.jobs.contexto import ContextoJob
from votosbr.etl.mappers.tipos import PessoaCore, VotacaoMapeada
from votosbr.sources.http import ErroFonte

log = structlog.get_logger(__name__)


class JobVotacoes[T](ABC):
    fonte: ClassVar[FonteDado]

    def __init__(self, ctx: ContextoJob) -> None:
        self.ctx = ctx
        self._pessoas: dict[str, int] = {}  # cache id externo do parlamentar -> pessoa_id

    @abstractmethod
    def listar(self, inicio: date, fim: date) -> list[T]:
        """Votações com data em [inicio, fim]."""

    @abstractmethod
    def id_externo(self, item: T) -> str: ...

    @abstractmethod
    def mapear(self, item: T) -> tuple[VotacaoMapeada, int | None]:
        """Votação mapeada e o `raw_documento_id` que a originou. Pode fazer I/O na fonte."""

    @abstractmethod
    def buscar_pessoa(self, id_externo: str) -> PessoaCore: ...

    def processar_fatia(self, inicio: date, fim: date) -> bool:
        log.info("fatia.inicio", inicio=inicio.isoformat(), fim=fim.isoformat())
        try:
            itens = self.listar(inicio, fim)
        except ErroFonte as exc:
            self.ctx.execucao.erro("fatia.listagem_falhou", inicio=inicio, fim=fim, erro=str(exc))
            return False

        ok = True
        for item in itens:
            self.ctx.execucao.lidos += 1
            try:
                self.processar_votacao(item)
                self.ctx.execucao.gravados += 1
            except Exception as exc:  # tolerância a falhas parciais (seção 0.2.5)
                ok = False
                self.ctx.execucao.erro(
                    "votacao.falhou", id_externo=self.id_externo(item), erro=repr(exc)
                )
        log.info("fatia.fim", inicio=inicio.isoformat(), fim=fim.isoformat(), votacoes=len(itens))
        return ok

    def processar_votacao(self, item: T) -> None:
        # Toda a rede antes da transação: nada de conexão aberta esperando HTTP.
        mapeada, raw_id = self.mapear(item)
        novas_pessoas = self._buscar_pessoas_desconhecidas(mapeada)

        with self.ctx.fabrica() as s, s.begin():
            criadas = {
                id_ext: loaders.upsert_pessoa(s, p, self.fonte, id_ext)
                for id_ext, p in novas_pessoas.items()
            }
            self._gravar(s, mapeada, raw_id, {**self._pessoas, **criadas})
        self._pessoas.update(criadas)  # só após o commit

    def _buscar_pessoas_desconhecidas(self, mapeada: VotacaoMapeada) -> dict[str, PessoaCore]:
        ids = {v.id_externo_pessoa for v in mapeada.votos} - self._pessoas.keys()
        if not ids:
            return {}
        with self.ctx.fabrica() as s:
            self._pessoas.update(loaders.pessoas_por_id_externo(s, self.fonte, sorted(ids)))
        novas: dict[str, PessoaCore] = {}
        for id_ext in sorted(ids - self._pessoas.keys()):
            novas[id_ext] = self.buscar_pessoa(id_ext)
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
                loaders.resolver_partido(s, self.fonte, o.bancada_sigla, v.data)
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
            partido_id = loaders.resolver_partido(s, self.fonte, voto.partido_sigla_fonte, v.data)
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
            loaders.registrar_nao_mapeado(s, self.fonte, nm.campo, nm.valor, nm.exemplo_ref)
            self.ctx.execucao.alerta(
                "valor_nao_mapeado", campo=nm.campo, valor=nm.valor, ref=nm.exemplo_ref
            )
