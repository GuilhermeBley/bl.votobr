"""Tipos enumerados do domínio (seção 5.3). Valores em MAIÚSCULAS, iguais aos do PostgreSQL."""

from enum import StrEnum


class Casa(StrEnum):
    CAMARA = "CAMARA"
    SENADO = "SENADO"
    CONGRESSO = "CONGRESSO"


class FonteDado(StrEnum):
    CAMARA = "CAMARA"
    SENADO = "SENADO"
    CONGRESSO = "CONGRESSO"
    LEXML = "LEXML"
    TSE = "TSE"
    CURADORIA = "CURADORIA"


class VotoTipo(StrEnum):
    SIM = "SIM"
    NAO = "NAO"
    ABSTENCAO = "ABSTENCAO"
    OBSTRUCAO = "OBSTRUCAO"
    PRESIDENTE = "PRESIDENTE"
    PRESENTE_SEM_VOTO = "PRESENTE_SEM_VOTO"
    NAO_REGISTROU = "NAO_REGISTROU"
    AUSENTE = "AUSENTE"
    AUSENTE_JUSTIFICADO = "AUSENTE_JUSTIFICADO"
    SECRETO = "SECRETO"
    OUTRO = "OUTRO"


class OrientacaoTipo(StrEnum):
    SIM = "SIM"
    NAO = "NAO"
    ABSTENCAO = "ABSTENCAO"
    OBSTRUCAO = "OBSTRUCAO"
    LIBERADO = "LIBERADO"
    OUTRO = "OUTRO"


class VotacaoModalidade(StrEnum):
    NOMINAL = "NOMINAL"
    SIMBOLICA = "SIMBOLICA"
    SECRETA = "SECRETA"
    DESCONHECIDA = "DESCONHECIDA"


class VotacaoObjeto(StrEnum):
    TEXTO_BASE = "TEXTO_BASE"
    EMENDA = "EMENDA"
    DESTAQUE = "DESTAQUE"
    REDACAO_FINAL = "REDACAO_FINAL"
    URGENCIA = "URGENCIA"
    REQUERIMENTO_PROCEDIMENTAL = "REQUERIMENTO_PROCEDIMENTAL"
    PARECER = "PARECER"
    VETO = "VETO"
    OUTRO = "OUTRO"


class BancadaTipo(StrEnum):
    PARTIDO = "PARTIDO"
    BLOCO = "BLOCO"
    FEDERACAO = "FEDERACAO"
    GOVERNO = "GOVERNO"
    OPOSICAO = "OPOSICAO"
    MAIORIA = "MAIORIA"
    MINORIA = "MINORIA"
    OUTRA = "OUTRA"


class StatusExecucao(StrEnum):
    EXECUTANDO = "EXECUTANDO"
    SUCESSO = "SUCESSO"
    SUCESSO_COM_ALERTAS = "SUCESSO_COM_ALERTAS"
    FALHA = "FALHA"


# Votos que expressam sentido (participação e alinhamento, seção 7.4).
VOTOS_COM_SENTIDO = frozenset({VotoTipo.SIM, VotoTipo.NAO, VotoTipo.ABSTENCAO, VotoTipo.OBSTRUCAO})
