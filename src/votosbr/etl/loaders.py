"""Upserts idempotentes (`INSERT ... ON CONFLICT DO UPDATE`). Rodar duas vezes não duplica nada."""

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from votosbr.db.models import (
    Bancada,
    IdentificadorExterno,
    Orientacao,
    PartidoAlias,
    Pessoa,
    Proposicao,
    ValorNaoMapeado,
    Votacao,
    VotacaoProposicao,
    Voto,
)
from votosbr.domain.enums import BancadaTipo, Casa, FonteDado, OrientacaoTipo
from votosbr.etl.mappers.tipos import PessoaCore, ProposicaoCore, VotacaoCore, VotoCore


def upsert_votacao(s: Session, v: VotacaoCore, raw_documento_id: int | None) -> int:
    valores = {
        "id_publico": v.id_publico,
        "casa": v.casa,
        "fonte": v.fonte,
        "id_externo": v.id_externo,
        "orgao_sigla": v.orgao_sigla,
        "data": v.data,
        "data_hora": v.data_hora,
        "descricao": v.descricao,
        "modalidade": v.modalidade,
        "objeto": v.objeto,
        "turno": v.turno,
        "aprovado": v.aprovado,
        "resultado_fonte": v.resultado_fonte,
        "placar_fonte": v.placar_fonte,
        "url_fonte": v.url_fonte,
        "raw_documento_id": raw_documento_id,
    }
    stmt = pg_insert(Votacao).values(**valores)
    # `principal`/`principal_origem` pertencem à classificação/curadoria: nunca sobrescritos aqui.
    atualizar = {k: stmt.excluded[k] for k in valores if k not in ("fonte", "id_externo")}
    upsert = stmt.on_conflict_do_update(
        index_elements=[Votacao.fonte, Votacao.id_externo],
        set_={**atualizar, "atualizado_em": func.now(), "removido_na_fonte_em": None},
    ).returning(Votacao.id)
    return int(s.execute(upsert).scalar_one())


def upsert_proposicao(s: Session, p: ProposicaoCore, raw_documento_id: int | None) -> int:
    stmt = pg_insert(Proposicao).values(
        casa=p.casa,
        fonte=p.fonte,
        id_externo=p.id_externo,
        sigla_tipo=p.sigla_tipo,
        numero=p.numero,
        ano=p.ano,
        ementa=p.ementa,
        data_apresentacao=p.data_apresentacao,
        url_fonte=p.url_fonte,
        raw_documento_id=raw_documento_id,
    )
    upsert = stmt.on_conflict_do_update(
        index_elements=[Proposicao.fonte, Proposicao.id_externo],
        set_={
            "sigla_tipo": stmt.excluded.sigla_tipo,
            "numero": stmt.excluded.numero,
            "ano": stmt.excluded.ano,
            # Dados resumidos não apagam o que um detalhe mais completo já gravou.
            "ementa": func.coalesce(stmt.excluded.ementa, Proposicao.ementa),
            "data_apresentacao": func.coalesce(
                stmt.excluded.data_apresentacao, Proposicao.data_apresentacao
            ),
            "url_fonte": func.coalesce(stmt.excluded.url_fonte, Proposicao.url_fonte),
            "atualizado_em": func.now(),
        },
    ).returning(Proposicao.id)
    return int(s.execute(upsert).scalar_one())


def ligar_votacao_proposicao(s: Session, votacao_id: int, proposicao_id: int, papel: str) -> None:
    s.execute(
        pg_insert(VotacaoProposicao)
        .values(votacao_id=votacao_id, proposicao_id=proposicao_id, papel=papel)
        .on_conflict_do_nothing()
    )


def obter_ou_criar_bancada(
    s: Session, casa: Casa, sigla: str, tipo: BancadaTipo, partido_id: int | None
) -> int:
    stmt = pg_insert(Bancada).values(casa=casa, sigla=sigla, tipo=tipo, partido_id=partido_id)
    upsert = stmt.on_conflict_do_update(
        index_elements=[Bancada.casa, Bancada.sigla],
        set_={
            "tipo": stmt.excluded.tipo,
            "partido_id": func.coalesce(stmt.excluded.partido_id, Bancada.partido_id),
        },
    ).returning(Bancada.id)
    return int(s.execute(upsert).scalar_one())


def upsert_orientacao(
    s: Session, votacao_id: int, bancada_id: int, orientacao: OrientacaoTipo, original: str
) -> None:
    stmt = pg_insert(Orientacao).values(
        votacao_id=votacao_id,
        bancada_id=bancada_id,
        orientacao=orientacao,
        orientacao_original=original,
    )
    s.execute(
        stmt.on_conflict_do_update(
            index_elements=[Orientacao.votacao_id, Orientacao.bancada_id],
            set_={
                "orientacao": stmt.excluded.orientacao,
                "orientacao_original": stmt.excluded.orientacao_original,
            },
        )
    )


def upsert_voto(
    s: Session, votacao_id: int, pessoa_id: int, v: VotoCore, partido_id: int | None
) -> None:
    stmt = pg_insert(Voto).values(
        votacao_id=votacao_id,
        pessoa_id=pessoa_id,
        voto=v.voto,
        voto_original=v.voto_original,
        derivado=False,
        partido_id=partido_id,
        partido_sigla_fonte=v.partido_sigla_fonte,
        uf=v.uf,
        registrado_em=v.registrado_em,
    )
    s.execute(
        stmt.on_conflict_do_update(
            index_elements=[Voto.votacao_id, Voto.pessoa_id],
            set_={
                k: stmt.excluded[k]
                for k in (
                    "voto",
                    "voto_original",
                    "derivado",
                    "partido_id",
                    "partido_sigla_fonte",
                    "uf",
                    "registrado_em",
                )
            },
        )
    )


def registrar_nao_mapeado(
    s: Session, fonte: FonteDado, campo: str, valor: str, exemplo_ref: str
) -> None:
    stmt = pg_insert(ValorNaoMapeado).values(
        fonte=fonte, campo=campo, valor=valor, exemplo_ref=exemplo_ref
    )
    s.execute(
        stmt.on_conflict_do_update(
            index_elements=[ValorNaoMapeado.fonte, ValorNaoMapeado.campo, ValorNaoMapeado.valor],
            set_={
                "ocorrencias": ValorNaoMapeado.ocorrencias + 1,
                "ultima_ocorrencia": func.now(),
            },
        )
    )


def resolver_partido(s: Session, fonte: FonteDado, sigla: str | None, data: date) -> int | None:
    """Sigla da fonte + data -> alias válido na data -> partido_id (seção 6.6)."""
    if not sigla:
        return None
    return s.scalar(
        select(PartidoAlias.partido_id)
        .where(
            PartidoAlias.fonte == fonte,
            PartidoAlias.sigla == sigla,
            or_(PartidoAlias.valido_de.is_(None), PartidoAlias.valido_de <= data),
            or_(PartidoAlias.valido_ate.is_(None), PartidoAlias.valido_ate >= data),
        )
        .order_by(PartidoAlias.valido_de.desc().nulls_last())
        .limit(1)
    )


def pessoas_por_id_externo(s: Session, fonte: FonteDado, ids: list[str]) -> dict[str, int]:
    linhas = s.execute(
        select(IdentificadorExterno.id_externo, IdentificadorExterno.pessoa_id).where(
            IdentificadorExterno.fonte == fonte, IdentificadorExterno.id_externo.in_(ids)
        )
    )
    return {id_externo: pessoa_id for id_externo, pessoa_id in linhas}


def _slug_livre(s: Session, base: str) -> str:
    """Slug imutável; colisão ganha sufixo numérico (seção 5.2)."""
    existentes = set(s.scalars(select(Pessoa.slug).where(Pessoa.slug.like(f"{base}%"))))
    if base not in existentes:
        return base
    n = 2
    while f"{base}-{n}" in existentes:
        n += 1
    return f"{base}-{n}"


def upsert_pessoa(s: Session, p: PessoaCore, fonte: FonteDado, id_externo: str) -> int:
    """Mesmo (fonte, id_externo) -> mesma pessoa. O slug nunca muda depois de criado."""
    existente = s.scalar(
        select(IdentificadorExterno.pessoa_id).where(
            IdentificadorExterno.fonte == fonte, IdentificadorExterno.id_externo == id_externo
        )
    )
    if existente is not None:
        pessoa = s.get_one(Pessoa, existente)
        pessoa.nome_civil = p.nome_civil
        pessoa.nome_parlamentar = p.nome_parlamentar
        pessoa.nome_busca = p.nome_busca
        pessoa.data_nascimento = p.data_nascimento
        pessoa.sexo = p.sexo
        pessoa.uf_nascimento = p.uf_nascimento
        pessoa.municipio_nascimento = p.municipio_nascimento
        pessoa.url_foto = p.url_foto
        return existente

    pessoa = Pessoa(
        slug=_slug_livre(s, p.slug_base),
        nome_civil=p.nome_civil,
        nome_parlamentar=p.nome_parlamentar,
        nome_busca=p.nome_busca,
        data_nascimento=p.data_nascimento,
        sexo=p.sexo,
        uf_nascimento=p.uf_nascimento,
        municipio_nascimento=p.municipio_nascimento,
        url_foto=p.url_foto,
    )
    s.add(pessoa)
    s.flush()
    s.add(IdentificadorExterno(pessoa_id=pessoa.id, fonte=fonte, id_externo=id_externo))
    s.flush()
    return pessoa.id
