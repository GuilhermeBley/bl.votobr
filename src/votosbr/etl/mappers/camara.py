"""Mappers puros Câmara (staging) -> core. Sem I/O."""

import re
from typing import Any

from votosbr.domain.classificacao import ClassificadorObjeto, classificar_modalidade
from votosbr.domain.enums import BancadaTipo, Casa, FonteDado
from votosbr.domain.normalizacao import Normalizador
from votosbr.domain.tempo import em_brasilia
from votosbr.domain.texto import chave_comparacao, slugificar
from votosbr.etl.mappers.tipos import (
    NaoMapeado,
    OrientacaoCore,
    PessoaCore,
    ProposicaoCore,
    VotacaoCore,
    VotacaoMapeada,
    VotoCore,
)
from votosbr.sources.camara.schemas import (
    DeputadoDetalhe,
    OrientacaoCamara,
    ProposicaoResumo,
    VotacaoDetalhe,
    VotacaoResumo,
    VotoCamara,
)

FONTE = FonteDado.CAMARA
CASA = Casa.CAMARA

# Placar citado no fim da descrição: "... Sim: 461; Não: 4; Total: 465."
_PLACAR = re.compile(r"\b(Sim|Não|Abstenção|Obstrução|Total)\s*:\s*(\d+)")

_BANCADAS_ESPECIAIS = {
    "governo": BancadaTipo.GOVERNO,
    "oposicao": BancadaTipo.OPOSICAO,
    "maioria": BancadaTipo.MAIORIA,
    "minoria": BancadaTipo.MINORIA,
}


def id_publico(id_externo: str) -> str:
    return f"camara-{id_externo}"


def extrair_placar(descricao: str | None) -> dict[str, Any] | None:
    if not descricao:
        return None
    placar = {rotulo: int(n) for rotulo, n in _PLACAR.findall(descricao)}
    return placar or None


def tipo_bancada(orientacao: OrientacaoCamara) -> BancadaTipo:
    if orientacao.codTipoLideranca == "P":
        return BancadaTipo.PARTIDO
    chave = chave_comparacao(orientacao.siglaPartidoBloco)
    if chave in _BANCADAS_ESPECIAIS:
        return _BANCADAS_ESPECIAIS[chave]
    if chave.startswith("fdr"):
        return BancadaTipo.FEDERACAO
    if chave.startswith("bl"):
        return BancadaTipo.BLOCO
    return BancadaTipo.OUTRA


def mapear_proposicao(p: ProposicaoResumo) -> ProposicaoCore:
    return ProposicaoCore(
        casa=CASA,
        fonte=FONTE,
        id_externo=str(p.id),
        sigla_tipo=p.siglaTipo,
        numero=p.numero,
        ano=p.ano,
        ementa=p.ementa,
        data_apresentacao=p.dataApresentacao.date() if p.dataApresentacao else None,
        url_fonte=p.uri,
    )


def _proposicoes(
    resumo: VotacaoResumo | None, detalhe: VotacaoDetalhe
) -> list[tuple[ProposicaoCore, str]]:
    resultado = [(mapear_proposicao(p), "AFETADA") for p in detalhe.proposicoesAfetadas]
    # O objeto votado só vem na listagem (`uriProposicaoObjeto`); o detalhe traz os candidatos.
    if resumo and resumo.uriProposicaoObjeto:
        id_objeto = resumo.uriProposicaoObjeto.rstrip("/").rsplit("/", 1)[-1]
        objeto = next((p for p in detalhe.objetosPossiveis if str(p.id) == id_objeto), None)
        if objeto is not None:
            resultado.append((mapear_proposicao(objeto), "OBJETO"))
    return resultado


def mapear_votacao(
    resumo: VotacaoResumo | None,
    detalhe: VotacaoDetalhe,
    votos: list[VotoCamara],
    orientacoes: list[OrientacaoCamara],
    normalizador: Normalizador,
    classificador: ClassificadorObjeto,
) -> VotacaoMapeada:
    ref = detalhe.id
    nao_mapeados: list[NaoMapeado] = []

    votos_core: list[VotoCore] = []
    for v in votos:
        n = normalizador.voto(FONTE, v.tipoVoto)
        if not n.mapeado:
            nao_mapeados.append(NaoMapeado("voto", v.tipoVoto, ref))
        votos_core.append(
            VotoCore(
                id_externo_pessoa=str(v.deputado_.id),
                voto=n.valor,
                voto_original=v.tipoVoto,
                mapeado=n.mapeado,
                partido_sigla_fonte=v.deputado_.siglaPartido,
                uf=v.deputado_.siglaUf,
                registrado_em=em_brasilia(v.dataRegistroVoto),
            )
        )

    orientacoes_core: list[OrientacaoCore] = []
    for o in orientacoes:
        if not o.orientacaoVoto.strip():
            continue  # bancada não orientou (decisão 009)
        n_o = normalizador.orientacao(FONTE, o.orientacaoVoto)
        if not n_o.mapeado:
            nao_mapeados.append(NaoMapeado("orientacao", o.orientacaoVoto, ref))
        orientacoes_core.append(
            OrientacaoCore(
                bancada_sigla=o.siglaPartidoBloco,
                bancada_tipo=tipo_bancada(o),
                orientacao=n_o.valor,
                orientacao_original=o.orientacaoVoto,
                mapeado=n_o.mapeado,
            )
        )

    classificacao = classificador.classificar(detalhe.descricao)
    votacao = VotacaoCore(
        id_publico=id_publico(detalhe.id),
        casa=CASA,
        fonte=FONTE,
        id_externo=detalhe.id,
        orgao_sigla=detalhe.siglaOrgao,
        data=detalhe.data,
        data_hora=em_brasilia(detalhe.dataHoraRegistro),
        descricao=detalhe.descricao,
        modalidade=classificar_modalidade(
            (v.voto for v in votos_core), tem_resultado=detalhe.aprovacao is not None
        ),
        objeto=classificacao.objeto,
        turno=classificacao.turno,
        aprovado=None if detalhe.aprovacao is None else detalhe.aprovacao == 1,
        resultado_fonte=None if detalhe.aprovacao is None else str(detalhe.aprovacao),
        placar_fonte=extrair_placar(detalhe.descricao),
        url_fonte=detalhe.uri,
    )
    return VotacaoMapeada(
        votacao=votacao,
        votos=votos_core,
        orientacoes=orientacoes_core,
        proposicoes=_proposicoes(resumo, detalhe),
        nao_mapeados=nao_mapeados,
    )


def mapear_pessoa(d: DeputadoDetalhe) -> PessoaCore:
    nome = d.ultimoStatus.nome
    return PessoaCore(
        slug_base=slugificar(nome, d.ultimoStatus.siglaUf or ""),
        nome_civil=d.nomeCivil,
        nome_parlamentar=nome,
        nome_busca=chave_comparacao(nome),
        data_nascimento=d.dataNascimento,
        sexo=d.sexo,
        uf_nascimento=d.ufNascimento,
        municipio_nascimento=d.municipioNascimento,
        url_foto=d.ultimoStatus.urlFoto,
    )
