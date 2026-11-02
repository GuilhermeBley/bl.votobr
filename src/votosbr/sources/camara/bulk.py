"""Arquivos em massa da Câmara, para backfill histórico (T-104, etapa posterior ao incremental).

Padrão observado (validar antes de implementar):
`https://dadosabertos.camara.leg.br/arquivos/{conjunto}/{formato}/{conjunto}-{ano}.{formato}`
"""

URL_ARQUIVO = (
    "https://dadosabertos.camara.leg.br/arquivos/{conjunto}/{formato}/{conjunto}-{ano}.{formato}"
)

CONJUNTOS_VOTACOES = (
    "votacoes",
    "votacoesVotos",
    "votacoesOrientacoes",
    "votacoesObjetos",
    "votacoesProposicoes",
)


def url_arquivo(conjunto: str, ano: int, formato: str = "json") -> str:
    return URL_ARQUIVO.format(conjunto=conjunto, formato=formato, ano=ano)
