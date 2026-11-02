from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import aliased

from votosbr.api.deps import SessaoDep
from votosbr.api.schemas.comum import Envelope
from votosbr.api.schemas.referencia import LegislaturaOut, PartidoOut, TemaOut
from votosbr.db.models import Legislatura, Partido, Tema

router = APIRouter(tags=["referencia"])


@router.get("/legislaturas", response_model=Envelope[list[LegislaturaOut]])
def legislaturas(sessao: SessaoDep) -> Envelope[list[LegislaturaOut]]:
    itens = sessao.scalars(select(Legislatura).order_by(Legislatura.numero.desc()))
    return Envelope(
        data=[
            LegislaturaOut(numero=i.numero, data_inicio=i.data_inicio, data_fim=i.data_fim)
            for i in itens
        ]
    )


@router.get("/partidos", response_model=Envelope[list[PartidoOut]])
def partidos(sessao: SessaoDep) -> Envelope[list[PartidoOut]]:
    sucessor = aliased(Partido)
    linhas = sessao.execute(
        select(Partido, sucessor.slug)
        .outerjoin(sucessor, sucessor.id == Partido.sucessor_id)
        .order_by(Partido.sigla_atual)
    )
    return Envelope(
        data=[
            PartidoOut(
                slug=p.slug,
                sigla=p.sigla_atual,
                nome=p.nome,
                extinto_em=p.data_extincao,
                sucessor=slug_sucessor,
            )
            for p, slug_sucessor in linhas
        ]
    )


@router.get("/temas", response_model=Envelope[list[TemaOut]])
def temas(sessao: SessaoDep) -> Envelope[list[TemaOut]]:
    itens = sessao.scalars(select(Tema).order_by(Tema.nome))
    return Envelope(data=[TemaOut(slug=t.slug, nome=t.nome) for t in itens])
