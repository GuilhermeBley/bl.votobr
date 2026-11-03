"""Job `senado-votacoes`: incremental de votações de Plenário do Senado, com checkpoint (T-203).

`GET /votacao` já traz os votos embutidos: uma requisição por fatia. Senador desconhecido é
buscado sob demanda (`/senador/{codigo}`). Mesma pessoa em Câmara e Senado ainda gera dois
registros até a resolução entre Casas (T-205).
"""

from datetime import date

from votosbr.domain.enums import FonteDado
from votosbr.etl.jobs.votacoes import JobVotacoes
from votosbr.etl.mappers import senado as mapper
from votosbr.etl.mappers.tipos import PessoaCore, VotacaoMapeada
from votosbr.sources.senado.schemas import VotacaoSenado

JOB = "senado-votacoes"

ItemSenado = tuple[VotacaoSenado, int | None]


class JobSenadoVotacoes(JobVotacoes[ItemSenado]):
    fonte = FonteDado.SENADO

    def listar(self, inicio: date, fim: date) -> list[ItemSenado]:
        return self.ctx.senado.votacoes(inicio, fim)

    def id_externo(self, item: ItemSenado) -> str:
        return str(item[0].codigoSessaoVotacao)

    def mapear(self, item: ItemSenado) -> tuple[VotacaoMapeada, int | None]:
        votacao, raw_id = item
        return mapper.mapear_votacao(votacao, self.ctx.normalizador, self.ctx.classificador), raw_id

    def buscar_pessoa(self, id_externo: str) -> PessoaCore:
        senador, _ = self.ctx.senado.senador(int(id_externo))
        return mapper.mapear_pessoa(senador)
