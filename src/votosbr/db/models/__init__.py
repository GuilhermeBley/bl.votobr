"""Modelos ORM. Importar este pacote registra todas as tabelas em `Base.metadata`."""

from votosbr.db.models.curadoria import (
    CuradoriaLog,
    PessoaMatchCandidato,
    ProcessoTema,
    SlugAlias,
    Tema,
)
from votosbr.db.models.ingestao import (
    CheckpointIngestao,
    ExecucaoIngestao,
    RawDocumento,
    ResultadoCheck,
    ValorNaoMapeado,
)
from votosbr.db.models.pessoa import Exercicio, Filiacao, IdentificadorExterno, Mandato, Pessoa
from votosbr.db.models.proposicao import Norma, ProcessoLegislativo, Proposicao, ProposicaoRelacao
from votosbr.db.models.referencia import Bancada, BancadaMembro, Legislatura, Partido, PartidoAlias
from votosbr.db.models.votacao import Orientacao, Votacao, VotacaoProposicao, Voto

__all__ = [
    "Bancada",
    "BancadaMembro",
    "CheckpointIngestao",
    "CuradoriaLog",
    "ExecucaoIngestao",
    "Exercicio",
    "Filiacao",
    "IdentificadorExterno",
    "Legislatura",
    "Mandato",
    "Norma",
    "Orientacao",
    "Partido",
    "PartidoAlias",
    "Pessoa",
    "PessoaMatchCandidato",
    "ProcessoLegislativo",
    "ProcessoTema",
    "Proposicao",
    "ProposicaoRelacao",
    "RawDocumento",
    "ResultadoCheck",
    "SlugAlias",
    "Tema",
    "ValorNaoMapeado",
    "Votacao",
    "VotacaoProposicao",
    "Voto",
]
