"""Controle de ingestão no banco: execuções, checkpoints e registro de documentos brutos."""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from votosbr.db.models import CheckpointIngestao, ExecucaoIngestao, RawDocumento
from votosbr.domain.enums import FonteDado, StatusExecucao

log = structlog.get_logger(__name__)

MAX_OCORRENCIAS_GRAVADAS = 500


class Execucao:
    """Uma linha em `execucao_ingestao` por comando. Uso: `with Execucao(...) as ex:`."""

    def __init__(
        self, fabrica: sessionmaker[Session], job: str, parametros: Mapping[str, Any]
    ) -> None:
        self._fabrica = fabrica
        self.job = job
        self.parametros = dict(parametros)
        self.id: int | None = None
        self.lidos = 0
        self.gravados = 0
        self.ocorrencias: list[dict[str, Any]] = []
        self._tem_erro = False

    def __enter__(self) -> "Execucao":
        with self._fabrica() as s, s.begin():
            registro = ExecucaoIngestao(
                job=self.job,
                parametros=_serializavel(self.parametros),
                status=StatusExecucao.EXECUTANDO.value,
            )
            s.add(registro)
            s.flush()
            self.id = registro.id
        structlog.contextvars.bind_contextvars(execucao_id=self.id, job=self.job)
        log.info("execucao.inicio", parametros=self.parametros)
        return self

    def alerta(self, tipo: str, **contexto: Any) -> None:
        log.warning(tipo, **contexto)
        self._registrar("ALERTA", tipo, contexto)

    def erro(self, tipo: str, **contexto: Any) -> None:
        log.error(tipo, **contexto)
        self._tem_erro = True
        self._registrar("ERRO", tipo, contexto)

    def _registrar(self, severidade: str, tipo: str, contexto: dict[str, Any]) -> None:
        if len(self.ocorrencias) < MAX_OCORRENCIAS_GRAVADAS:
            self.ocorrencias.append(
                {"severidade": severidade, "tipo": tipo, **_serializavel(contexto)}
            )

    def __exit__(
        self,
        tipo_exc: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is not None:
            status = StatusExecucao.FALHA
            self._registrar("ERRO", "excecao", {"erro": repr(exc)})
        elif self._tem_erro or self.ocorrencias:
            status = StatusExecucao.SUCESSO_COM_ALERTAS
        else:
            status = StatusExecucao.SUCESSO
        with self._fabrica() as s, s.begin():
            registro = s.get_one(ExecucaoIngestao, self.id)
            registro.fim = datetime.now(UTC)
            registro.status = status.value
            registro.registros_lidos = self.lidos
            registro.registros_gravados = self.gravados
            registro.erros = self.ocorrencias or None
        log.info("execucao.fim", status=status.value, lidos=self.lidos, gravados=self.gravados)
        structlog.contextvars.unbind_contextvars("execucao_id", "job")

    @property
    def teve_erro(self) -> bool:
        return self._tem_erro


class SqlCheckpointRepo:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def obter(self, job: str) -> date | None:
        with self._fabrica() as s:
            return s.scalar(
                select(CheckpointIngestao.processado_ate).where(CheckpointIngestao.job == job)
            )

    def avancar(self, job: str, data: date, execucao_id: int | None = None) -> None:
        stmt = pg_insert(CheckpointIngestao).values(
            job=job, processado_ate=data, execucao_id=execucao_id
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[CheckpointIngestao.job],
            set_={
                "processado_ate": func.greatest(
                    CheckpointIngestao.processado_ate, stmt.excluded.processado_ate
                ),
                "execucao_id": stmt.excluded.execucao_id,
                "atualizado_em": func.now(),
            },
        )
        with self._fabrica() as s, s.begin():
            s.execute(stmt)

    def definir(self, job: str, data: date, execucao_id: int | None = None) -> None:
        """Ajuste manual (`votosbr checkpoint definir`): pode recuar."""
        stmt = pg_insert(CheckpointIngestao).values(
            job=job, processado_ate=data, execucao_id=execucao_id
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[CheckpointIngestao.job],
            set_={
                "processado_ate": stmt.excluded.processado_ate,
                "execucao_id": stmt.excluded.execucao_id,
                "atualizado_em": func.now(),
            },
        )
        with self._fabrica() as s, s.begin():
            s.execute(stmt)

    def todos(self) -> list[CheckpointIngestao]:
        with self._fabrica() as s:
            return list(s.scalars(select(CheckpointIngestao).order_by(CheckpointIngestao.job)))


class SqlRegistroRaw:
    """Registra `raw_documento` em transação própria: o registro sobrevive a rollback da carga."""

    def __init__(self, fabrica: sessionmaker[Session], execucao_id: int | None) -> None:
        self._fabrica = fabrica
        self._execucao_id = execucao_id

    def registrar(
        self,
        *,
        fonte: FonteDado,
        url: str,
        parametros: Mapping[str, Any] | None,
        http_status: int,
        conteudo_hash: str,
        caminho_storage: str,
    ) -> int:
        with self._fabrica() as s, s.begin():
            doc = RawDocumento(
                fonte=fonte,
                url=url,
                parametros=_serializavel(dict(parametros)) if parametros else None,
                http_status=http_status,
                conteudo_hash=conteudo_hash,
                caminho_storage=caminho_storage,
                execucao_id=self._execucao_id,
            )
            s.add(doc)
            s.flush()
            return doc.id


def _serializavel(valor: Any) -> Any:
    if isinstance(valor, Mapping):
        return {str(k): _serializavel(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_serializavel(v) for v in valor]
    if isinstance(valor, date | datetime):
        return valor.isoformat()
    if valor is None or isinstance(valor, str | int | float | bool):
        return valor
    return str(valor)
