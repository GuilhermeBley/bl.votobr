"""Rótulos em português dos enums, servidos por GET /meta/enums (o frontend não fixa rótulos)."""

from enum import StrEnum

from votosbr.domain.enums import (
    BancadaTipo,
    Casa,
    OrientacaoTipo,
    VotacaoModalidade,
    VotacaoObjeto,
    VotoTipo,
)

ROTULOS: dict[type[StrEnum], dict[str, str]] = {
    Casa: {
        "CAMARA": "Câmara dos Deputados",
        "SENADO": "Senado Federal",
        "CONGRESSO": "Congresso Nacional",
    },
    VotoTipo: {
        "SIM": "Sim",
        "NAO": "Não",
        "ABSTENCAO": "Abstenção",
        "OBSTRUCAO": "Obstrução",
        "PRESIDENTE": "Presidente da sessão",
        "PRESENTE_SEM_VOTO": "Presente, não registrou voto",
        "NAO_REGISTROU": "Não registrou voto",
        "AUSENTE": "Ausente",
        "AUSENTE_JUSTIFICADO": "Ausência justificada",
        "SECRETO": "Votou (votação secreta)",
        "OUTRO": "Outro",
    },
    OrientacaoTipo: {
        "SIM": "Sim",
        "NAO": "Não",
        "ABSTENCAO": "Abstenção",
        "OBSTRUCAO": "Obstrução",
        "LIBERADO": "Liberado",
        "OUTRO": "Outro",
    },
    VotacaoModalidade: {
        "NOMINAL": "Nominal",
        "SIMBOLICA": "Simbólica",
        "SECRETA": "Secreta",
        "DESCONHECIDA": "Desconhecida",
    },
    VotacaoObjeto: {
        "TEXTO_BASE": "Texto-base",
        "EMENDA": "Emenda",
        "DESTAQUE": "Destaque",
        "REDACAO_FINAL": "Redação final",
        "URGENCIA": "Requerimento de urgência",
        "REQUERIMENTO_PROCEDIMENTAL": "Requerimento procedimental",
        "PARECER": "Parecer",
        "VETO": "Veto",
        "OUTRO": "Outro",
    },
    BancadaTipo: {
        "PARTIDO": "Partido",
        "BLOCO": "Bloco",
        "FEDERACAO": "Federação",
        "GOVERNO": "Governo",
        "OPOSICAO": "Oposição",
        "MAIORIA": "Maioria",
        "MINORIA": "Minoria",
        "OUTRA": "Outra",
    },
}

# Agrupamento para exibição (seção 5.4); calculado, nunca armazenado.
GRUPO_EXIBICAO: dict[VotoTipo, str] = {
    VotoTipo.SIM: "A_FAVOR",
    VotoTipo.NAO: "CONTRA",
    VotoTipo.ABSTENCAO: "ABSTENCAO",
    VotoTipo.OBSTRUCAO: "OBSTRUCAO",
}
GRUPO_PADRAO = "NAO_VOTOU"
