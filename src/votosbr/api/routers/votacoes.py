"""Votações, votos e placares (seção 7.2). Placar calculado sobre `voto`; migra para as views
materializadas em T-403."""

import csv
import io
from collections import defaultdict
from datetime import date
from enum import StrEnum
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from votosbr.api.deps import PaginaDep, PorPaginaDep, SessaoDep
from votosbr.api.schemas.comum import NOME_FONTE, Aviso, Envelope, FonteOut, Meta, Paginacao
from votosbr.api.schemas.votacao import (
    GrupoPlacar,
    OrientacaoOut,
    ParlamentarRef,
    PartidoRef,
    PlacarPartido,
    ProcessoRef,
    ProposicaoRef,
    VotacaoDetalheOut,
    VotacaoResumoOut,
    VotoOut,
)
from votosbr.db.models import (
    Bancada,
    Orientacao,
    Partido,
    Pessoa,
    ProcessoLegislativo,
    Proposicao,
    RawDocumento,
    Votacao,
    VotacaoProposicao,
    Voto,
)
from votosbr.domain.enums import (
    VOTOS_COM_SENTIDO,
    BancadaTipo,
    Casa,
    OrientacaoTipo,
    VotacaoModalidade,
    VotoTipo,
)
from votosbr.domain.texto import chave_comparacao

router = APIRouter(prefix="/votacoes", tags=["votacoes"])

POR_PAGINA_MAX_VOTOS = 600  # a Câmara inteira numa chamada
_SENTIDOS = {v.value for v in VOTOS_COM_SENTIDO}

AVISOS = {
    "VOTACAO_SIMBOLICA": "Votação simbólica: não há registro individual de votos.",
    "VOTACAO_SECRETA": "Votação secreta: registra-se quem votou, mas não o sentido do voto.",
    "NAO_REGISTROU_DERIVADO": (
        "Deputados em exercício que não registraram voto; "
        "a Câmara não informa presença nesta votação."
    ),
}


class Ordenacao(StrEnum):
    DATA_DESC = "-data"
    DATA_ASC = "data"


class AgruparPor(StrEnum):
    PARTIDO = "partido"
    UF = "uf"


def _resumo(v: Votacao) -> VotacaoResumoOut:
    return VotacaoResumoOut(
        id=v.id_publico,
        casa=v.casa,
        orgao=v.orgao_sigla,
        data=v.data,
        data_hora=v.data_hora,
        descricao=v.descricao,
        modalidade=v.modalidade,
        objeto=v.objeto,
        turno=v.turno,
        principal=v.principal,
        aprovado=v.aprovado,
    )


def _obter(sessao: Session, id_publico: str) -> Votacao:
    votacao = sessao.scalar(select(Votacao).where(Votacao.id_publico == id_publico))
    if votacao is None or votacao.removido_na_fonte_em is not None:
        raise HTTPException(404, f"Votação '{id_publico}' não encontrada.")
    return votacao


def _contar(sessao: Session, stmt: Select[Any]) -> int:
    return sessao.scalar(select(func.count()).select_from(stmt.subquery())) or 0


@router.get("", response_model=Envelope[list[VotacaoResumoOut]])
def listar(
    sessao: SessaoDep,
    casa: Casa | None = None,
    de: date | None = None,
    ate: date | None = None,
    modalidade: VotacaoModalidade | None = None,
    principal: bool | None = None,
    ordenar: Ordenacao = Ordenacao.DATA_DESC,
    pagina: PaginaDep = 1,
    por_pagina: PorPaginaDep = 20,
) -> Envelope[list[VotacaoResumoOut]]:
    stmt = select(Votacao).where(Votacao.removido_na_fonte_em.is_(None))
    if casa:
        stmt = stmt.where(Votacao.casa == casa)
    if de:
        stmt = stmt.where(Votacao.data >= de)
    if ate:
        stmt = stmt.where(Votacao.data <= ate)
    if modalidade:
        stmt = stmt.where(Votacao.modalidade == modalidade)
    if principal is not None:
        stmt = stmt.where(Votacao.principal == principal)
    total = _contar(sessao, stmt)
    ordem = (
        (Votacao.data.desc(), Votacao.data_hora.desc().nulls_last())
        if ordenar == Ordenacao.DATA_DESC
        else (Votacao.data.asc(), Votacao.data_hora.asc().nulls_last())
    )
    itens = sessao.scalars(
        stmt.order_by(*ordem, Votacao.id_publico)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    )
    return Envelope(
        data=[_resumo(v) for v in itens],
        meta=Meta(paginacao=Paginacao.calcular(pagina, por_pagina, total)),
    )


@router.get("/{id_publico}", response_model=Envelope[VotacaoDetalheOut])
def detalhe(id_publico: str, sessao: SessaoDep) -> Envelope[VotacaoDetalheOut]:
    v = _obter(sessao, id_publico)

    placar: dict[VotoTipo, int] = dict(
        sessao.execute(
            select(Voto.voto, func.count()).where(Voto.votacao_id == v.id).group_by(Voto.voto)
        ).all()
    )
    tem_derivado = bool(
        sessao.scalar(select(func.count()).where(Voto.votacao_id == v.id, Voto.derivado.is_(True)))
    )

    orientacoes = sessao.execute(
        select(Bancada, Orientacao)
        .join(Orientacao, Orientacao.bancada_id == Bancada.id)
        .where(Orientacao.votacao_id == v.id)
        .order_by(Bancada.tipo, Bancada.sigla)
    ).all()
    orientacao_por_partido = {
        b.partido_id: o.orientacao for b, o in orientacoes if b.partido_id is not None
    }

    proposicoes = sessao.execute(
        select(Proposicao, VotacaoProposicao.papel)
        .join(VotacaoProposicao, VotacaoProposicao.proposicao_id == Proposicao.id)
        .where(VotacaoProposicao.votacao_id == v.id)
        .order_by(VotacaoProposicao.papel, Proposicao.sigla_tipo)
    ).all()
    processo = sessao.scalar(
        select(ProcessoLegislativo)
        .join(Proposicao, Proposicao.processo_id == ProcessoLegislativo.id)
        .join(VotacaoProposicao, VotacaoProposicao.proposicao_id == Proposicao.id)
        .where(VotacaoProposicao.votacao_id == v.id)
        .limit(1)
    )
    coletado_em = (
        sessao.scalar(select(RawDocumento.coletado_em).where(RawDocumento.id == v.raw_documento_id))
        if v.raw_documento_id
        else None
    )

    avisos = []
    if v.modalidade == VotacaoModalidade.SIMBOLICA:
        avisos.append(Aviso(codigo="VOTACAO_SIMBOLICA", mensagem=AVISOS["VOTACAO_SIMBOLICA"]))
    if v.modalidade == VotacaoModalidade.SECRETA:
        avisos.append(Aviso(codigo="VOTACAO_SECRETA", mensagem=AVISOS["VOTACAO_SECRETA"]))
    if tem_derivado:
        avisos.append(
            Aviso(codigo="NAO_REGISTROU_DERIVADO", mensagem=AVISOS["NAO_REGISTROU_DERIVADO"])
        )

    resumo = _resumo(v)
    return Envelope(
        data=VotacaoDetalheOut(
            **resumo.model_dump(),
            placar=placar,
            placar_por_partido=_placar_por_partido(sessao, v.id, orientacao_por_partido),
            orientacoes=[
                OrientacaoOut(
                    bancada=b.sigla,
                    tipo=b.tipo,
                    orientacao=o.orientacao,
                    orientacao_original=o.orientacao_original,
                )
                for b, o in orientacoes
            ],
            processo=ProcessoRef(slug=processo.slug, titulo=processo.titulo) if processo else None,
            proposicoes=[
                ProposicaoRef(
                    casa=p.casa, sigla=p.sigla_tipo, numero=p.numero, ano=p.ano, papel=papel
                )
                for p, papel in proposicoes
            ],
            avisos=avisos,
            fontes=[
                FonteOut(nome=NOME_FONTE[v.fonte.value], url=v.url_fonte, coletado_em=coletado_em)
            ],
        )
    )


def _placar_por_partido(
    sessao: Session, votacao_id: int, orientacao_por_partido: dict[int, OrientacaoTipo]
) -> list[PlacarPartido]:
    linhas = sessao.execute(
        select(
            Voto.partido_id,
            Partido.slug,
            Partido.sigla_atual,
            Voto.partido_sigla_fonte,
            Voto.voto,
            func.count(),
        )
        .outerjoin(Partido, Partido.id == Voto.partido_id)
        .where(Voto.votacao_id == votacao_id)
        .group_by(
            Voto.partido_id, Partido.slug, Partido.sigla_atual, Voto.partido_sigla_fonte, Voto.voto
        )
    )
    grupos: dict[tuple[int | None, str | None, str], dict[VotoTipo, int]] = defaultdict(dict)
    for partido_id, slug, sigla, sigla_fonte, voto, n in linhas:
        chave = (partido_id, slug, sigla or sigla_fonte or "S/PARTIDO")
        grupos[chave][voto] = grupos[chave].get(voto, 0) + n
    resultado = [
        PlacarPartido(
            partido=PartidoRef(slug=slug, sigla=sigla),
            orientacao=orientacao_por_partido.get(partido_id) if partido_id else None,
            contagem=contagem,
        )
        for (partido_id, slug, sigla), contagem in grupos.items()
    ]
    return sorted(resultado, key=lambda p: (-sum(p.contagem.values()), p.partido.sigla))


@router.get("/{id_publico}/votos", response_model=Envelope[list[VotoOut]])
def votos(
    id_publico: str,
    sessao: SessaoDep,
    partido: Annotated[str | None, Query(description="Slug ou sigla do partido.")] = None,
    uf: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    voto: VotoTipo | None = None,
    q: Annotated[str | None, Query(description="Parte do nome do parlamentar.")] = None,
    formato: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
    pagina: PaginaDep = 1,
    por_pagina: Annotated[int, Query(ge=1, le=POR_PAGINA_MAX_VOTOS)] = POR_PAGINA_MAX_VOTOS,
) -> Envelope[list[VotoOut]] | Response:
    v = _obter(sessao, id_publico)
    stmt = (
        select(Voto, Pessoa, Partido)
        .join(Pessoa, Pessoa.id == Voto.pessoa_id)
        .outerjoin(Partido, Partido.id == Voto.partido_id)
        .where(Voto.votacao_id == v.id)
    )
    if partido:
        stmt = stmt.where(
            (Partido.slug == partido.lower()) | (Voto.partido_sigla_fonte == partido.upper())
        )
    if uf:
        stmt = stmt.where(Voto.uf == uf.upper())
    if voto:
        stmt = stmt.where(Voto.voto == voto)
    if q:
        stmt = stmt.where(Pessoa.nome_busca.contains(chave_comparacao(q), autoescape=True))

    orientacao_por_partido: dict[int, OrientacaoTipo] = {
        partido_id: orientacao
        for partido_id, orientacao in sessao.execute(
            select(Bancada.partido_id, Orientacao.orientacao)
            .join(Orientacao, Orientacao.bancada_id == Bancada.id)
            .where(
                Orientacao.votacao_id == v.id,
                Bancada.tipo == BancadaTipo.PARTIDO,
                Bancada.partido_id.is_not(None),
            )
        )
        if partido_id is not None
    }

    total = sessao.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    linhas = sessao.execute(
        stmt.order_by(Pessoa.nome_busca).offset((pagina - 1) * por_pagina).limit(por_pagina)
    ).all()
    itens = [_voto_out(vt, p, pt, orientacao_por_partido) for vt, p, pt in linhas]

    if formato == "csv":
        return _csv(id_publico, itens)
    return Envelope(data=itens, meta=Meta(paginacao=Paginacao.calcular(pagina, por_pagina, total)))


def _voto_out(
    vt: Voto, p: Pessoa, pt: Partido | None, orientacoes: dict[int, OrientacaoTipo]
) -> VotoOut:
    orientacao = orientacoes.get(vt.partido_id) if vt.partido_id else None
    seguiu = None
    if orientacao is not None and orientacao.value in _SENTIDOS and vt.voto in VOTOS_COM_SENTIDO:
        seguiu = orientacao.value == vt.voto.value
    partido_ref = None
    if pt is not None:
        partido_ref = PartidoRef(slug=pt.slug, sigla=pt.sigla_atual)
    elif vt.partido_sigla_fonte:
        partido_ref = PartidoRef(slug=None, sigla=vt.partido_sigla_fonte)
    return VotoOut(
        parlamentar=ParlamentarRef(slug=p.slug, nome=p.nome_parlamentar, url_foto=p.url_foto),
        partido=partido_ref,
        uf=vt.uf,
        voto=vt.voto,
        voto_original=vt.voto_original,
        derivado=vt.derivado,
        orientacao_partido=orientacao,
        seguiu_orientacao_partido=seguiu,
    )


def _csv(id_publico: str, itens: list[VotoOut]) -> Response:
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(
        [
            "parlamentar",
            "slug",
            "partido",
            "uf",
            "voto",
            "voto_original",
            "derivado",
            "orientacao_partido",
            "seguiu_orientacao_partido",
        ]
    )
    for i in itens:
        escritor.writerow(
            [
                i.parlamentar.nome,
                i.parlamentar.slug,
                i.partido.sigla if i.partido else "",
                i.uf or "",
                i.voto.value,
                i.voto_original,
                i.derivado,
                i.orientacao_partido.value if i.orientacao_partido else "",
                "" if i.seguiu_orientacao_partido is None else i.seguiu_orientacao_partido,
            ]
        )
    return Response(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="votos-{id_publico}.csv"'},
    )


@router.get("/{id_publico}/placar", response_model=Envelope[list[GrupoPlacar]])
def placar(
    id_publico: str, sessao: SessaoDep, agrupar: AgruparPor = AgruparPor.PARTIDO
) -> Envelope[list[GrupoPlacar]]:
    v = _obter(sessao, id_publico)
    coluna = (
        func.coalesce(Partido.sigla_atual, Voto.partido_sigla_fonte, "S/PARTIDO")
        if agrupar == AgruparPor.PARTIDO
        else func.coalesce(Voto.uf, "S/UF")
    )
    linhas = sessao.execute(
        select(coluna, Voto.voto, func.count())
        .outerjoin(Partido, Partido.id == Voto.partido_id)
        .where(Voto.votacao_id == v.id)
        .group_by(coluna, Voto.voto)
    )
    grupos: dict[str, dict[VotoTipo, int]] = defaultdict(dict)
    for grupo, voto, n in linhas:
        grupos[grupo][voto] = n
    return Envelope(data=[GrupoPlacar(grupo=g, contagem=c) for g, c in sorted(grupos.items())])
