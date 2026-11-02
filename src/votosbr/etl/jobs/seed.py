"""Job `seed`: legislaturas, partidos (com aliases) e temas de seeds/*.yaml. Idempotente."""

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from votosbr.db.models import Legislatura, Partido, PartidoAlias, Tema
from votosbr.domain.enums import FonteDado
from votosbr.etl.jobs.contexto import ContextoJob

JOB = "seed"


def _yaml(caminho: Path) -> Any:
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or []


def executar(ctx: ContextoJob) -> None:
    dir_seeds = ctx.settings.dir_seeds
    with ctx.fabrica() as s, s.begin():
        _legislaturas(s, _yaml(dir_seeds / "legislaturas.yaml"))
        _partidos(s, _yaml(dir_seeds / "partidos.yaml"))
        _temas(s, _yaml(dir_seeds / "temas.yaml"))
    ctx.execucao.gravados += 1


def _legislaturas(s: Session, itens: list[dict[str, Any]]) -> None:
    for item in itens:
        stmt = pg_insert(Legislatura).values(**item)
        s.execute(
            stmt.on_conflict_do_update(
                index_elements=[Legislatura.numero],
                set_={"data_inicio": stmt.excluded.data_inicio, "data_fim": stmt.excluded.data_fim},
            )
        )


def _partidos(s: Session, itens: list[dict[str, Any]]) -> None:
    ids: dict[str, int] = {}
    for item in itens:
        stmt = pg_insert(Partido).values(
            slug=item["slug"],
            sigla_atual=item["sigla_atual"],
            nome=item.get("nome"),
            numero_eleitoral=item.get("numero_eleitoral"),
            data_registro=item.get("data_registro"),
            data_extincao=item.get("data_extincao"),
        )
        upsert = stmt.on_conflict_do_update(
            index_elements=[Partido.slug],
            set_={
                c: stmt.excluded[c]
                for c in (
                    "sigla_atual",
                    "nome",
                    "numero_eleitoral",
                    "data_registro",
                    "data_extincao",
                )
            },
        ).returning(Partido.id)
        ids[item["slug"]] = int(s.execute(upsert).scalar_one())

    for item in itens:
        partido = s.get_one(Partido, ids[item["slug"]])
        partido.sucessor_id = ids[item["sucessor"]] if item.get("sucessor") else None
        for alias in item.get("aliases", []):
            _alias(s, partido.id, alias)


def _alias(s: Session, partido_id: int, alias: dict[str, Any]) -> None:
    # UNIQUE (fonte, sigla, valido_de) não protege valido_de nulo: busca explícita.
    fonte = FonteDado(alias["fonte"])
    valido_de = alias.get("valido_de")
    filtro_de = (
        PartidoAlias.valido_de.is_(None)
        if valido_de is None
        else PartidoAlias.valido_de == valido_de
    )
    existente = s.scalar(
        select(PartidoAlias).where(
            PartidoAlias.fonte == fonte, PartidoAlias.sigla == alias["sigla"], filtro_de
        )
    )
    if existente is None:
        existente = PartidoAlias(fonte=fonte, sigla=alias["sigla"], valido_de=valido_de)
        s.add(existente)
    existente.partido_id = partido_id
    existente.id_externo = alias.get("id_externo")
    existente.valido_ate = alias.get("valido_ate")


def _temas(s: Session, itens: list[dict[str, Any]]) -> None:
    for item in itens:
        stmt = pg_insert(Tema).values(slug=item["slug"], nome=item["nome"])
        s.execute(
            stmt.on_conflict_do_update(
                index_elements=[Tema.slug], set_={"nome": stmt.excluded.nome}
            )
        )
