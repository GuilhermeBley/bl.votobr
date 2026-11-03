"""Job `camara-votacoes`: incremental de votações de Plenário via API, com checkpoint (T-103).

Para cada votação: detalhe + votos + orientações -> mapper puro -> upserts (ver `JobVotacoes`).
Parlamentar desconhecido é buscado sob demanda (`/deputados/{id}`).
"""

from datetime import date

from votosbr.domain.enums import FonteDado
from votosbr.etl.jobs.votacoes import JobVotacoes
from votosbr.etl.mappers import camara as mapper
from votosbr.etl.mappers.tipos import PessoaCore, VotacaoMapeada
from votosbr.sources.camara.schemas import VotacaoResumo

JOB = "camara-votacoes"


class JobCamaraVotacoes(JobVotacoes[VotacaoResumo]):
    fonte = FonteDado.CAMARA

    def listar(self, inicio: date, fim: date) -> list[VotacaoResumo]:
        return [resumo for resumo, _raw in self.ctx.camara.votacoes(inicio, fim)]

    def id_externo(self, item: VotacaoResumo) -> str:
        return item.id

    def mapear(self, item: VotacaoResumo) -> tuple[VotacaoMapeada, int | None]:
        camara = self.ctx.camara
        detalhe, raw_id = camara.votacao(item.id)
        mapeada = mapper.mapear_votacao(
            item,
            detalhe,
            camara.votos(item.id),
            camara.orientacoes(item.id),
            self.ctx.normalizador,
            self.ctx.classificador,
        )
        return mapeada, raw_id

    def buscar_pessoa(self, id_externo: str) -> PessoaCore:
        deputado, _ = self.ctx.camara.deputado(int(id_externo))
        return mapper.mapear_pessoa(deputado)
