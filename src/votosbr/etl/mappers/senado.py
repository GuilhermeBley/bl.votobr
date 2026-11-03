"""Mappers puros Senado (staging) -> core. Sem I/O."""

from votosbr.domain.classificacao import ClassificadorObjeto, classificar_modalidade
from votosbr.domain.enums import Casa, FonteDado
from votosbr.domain.normalizacao import Normalizador
from votosbr.domain.texto import chave_comparacao, slugificar
from votosbr.etl.mappers.tipos import (
    NaoMapeado,
    PessoaCore,
    ProposicaoCore,
    VotacaoCore,
    VotacaoMapeada,
    VotoCore,
)
from votosbr.sources.senado.client import BASE_URL
from votosbr.sources.senado.schemas import Senador, VotacaoSenado

FONTE = FonteDado.SENADO
CASA = Casa.SENADO

# `GET /votacao` só cobre o Plenário; o informe legislativo confirma ("PLEN") quando presente.
ORGAO_PLENARIO = "PLEN"
SEM_PARTIDO = "S/Partido"
_RESULTADO = {"A": True, "R": False}
_SEXO = {"masculino": "M", "feminino": "F"}


def id_publico(id_externo: str) -> str:
    return f"senado-{id_externo}"


def _placar(v: VotacaoSenado) -> dict[str, int] | None:
    placar = {
        rotulo: n
        for rotulo, n in (
            ("Sim", v.totalVotosSim),
            ("Não", v.totalVotosNao),
            ("Abstenção", v.totalVotosAbstencao),
        )
        if n is not None
    }
    return placar or None


def _proposicao(v: VotacaoSenado) -> ProposicaoCore | None:
    if v.idProcesso is None or not v.sigla or not v.numero or not v.ano:
        return None
    return ProposicaoCore(
        casa=CASA,
        fonte=FONTE,
        id_externo=str(v.idProcesso),
        sigla_tipo=v.sigla,
        numero=int(v.numero),
        ano=v.ano,
        ementa=v.ementa,
        data_apresentacao=v.dataApresentacao,
        url_fonte=f"{BASE_URL}/processo/{v.idProcesso}",
    )


def mapear_votacao(
    v: VotacaoSenado, normalizador: Normalizador, classificador: ClassificadorObjeto
) -> VotacaoMapeada:
    ref = str(v.codigoSessaoVotacao)
    nao_mapeados: list[NaoMapeado] = []

    votos_core: list[VotoCore] = []
    for voto in v.votos:
        n = normalizador.voto(FONTE, voto.siglaVotoParlamentar)
        if not n.mapeado:
            nao_mapeados.append(NaoMapeado("voto", voto.siglaVotoParlamentar, ref))
        sigla = voto.siglaPartidoParlamentar
        votos_core.append(
            VotoCore(
                id_externo_pessoa=str(voto.codigoParlamentar),
                voto=n.valor,
                voto_original=voto.siglaVotoParlamentar,
                mapeado=n.mapeado,
                partido_sigla_fonte=None if sigla == SEM_PARTIDO else sigla,
                uf=voto.siglaUFParlamentar,
                registrado_em=None,  # a fonte não informa
            )
        )

    aprovado = _RESULTADO.get(v.resultadoVotacao or "")
    classificacao = classificador.classificar(v.descricaoVotacao)
    informe = v.informeLegislativo
    votacao = VotacaoCore(
        id_publico=id_publico(ref),
        casa=CASA,
        fonte=FONTE,
        id_externo=ref,
        orgao_sigla=(informe.siglaColegiado if informe else None) or ORGAO_PLENARIO,
        data=v.dataSessao,
        data_hora=None,  # `GET /votacao` não traz hora
        descricao=v.descricaoVotacao,
        modalidade=classificar_modalidade(
            (voto.voto for voto in votos_core),
            tem_resultado=v.resultadoVotacao is not None,
            secreta_na_fonte=v.votacaoSecreta == "S",
        ),
        objeto=classificacao.objeto,
        turno=classificacao.turno,
        aprovado=aprovado,
        resultado_fonte=v.resultadoVotacao,
        placar_fonte=_placar(v),
        url_fonte=None,  # a fonte não expõe URL própria da votação
    )
    proposicao = _proposicao(v)
    return VotacaoMapeada(
        votacao=votacao,
        votos=votos_core,
        orientacoes=[],  # pendente: `/plenario/votacao/orientacaoBancada` (docs/PENDENCIAS.md)
        proposicoes=[(proposicao, "OBJETO")] if proposicao else [],
        nao_mapeados=nao_mapeados,
    )


def mapear_pessoa(p: Senador) -> PessoaCore:
    ident = p.IdentificacaoParlamentar
    basicos = p.DadosBasicosParlamentar
    nome = ident.NomeParlamentar
    return PessoaCore(
        slug_base=slugificar(nome, ident.UfParlamentar or ""),
        nome_civil=ident.NomeCompletoParlamentar,
        nome_parlamentar=nome,
        nome_busca=chave_comparacao(nome),
        data_nascimento=basicos.DataNascimento if basicos else None,
        sexo=_SEXO.get(chave_comparacao(ident.SexoParlamentar or "")),
        uf_nascimento=basicos.UfNaturalidade if basicos else None,
        municipio_nascimento=basicos.Naturalidade if basicos else None,
        url_foto=ident.UrlFotoParlamentar,
    )
