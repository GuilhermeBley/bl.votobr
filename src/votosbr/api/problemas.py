"""Erros no formato problem details (RFC 9457, `application/problem+json`)."""

from collections.abc import Mapping
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

MEDIA_TYPE = "application/problem+json"

log = structlog.get_logger(__name__)


class Problema(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[dict[str, Any]] | None = None


_TITULOS = {
    400: "Requisição inválida",
    404: "Recurso não encontrado",
    405: "Método não permitido",
    422: "Parâmetros inválidos",
    429: "Muitas requisições",
    500: "Erro interno",
    503: "Serviço indisponível",
}


def resposta_problema(
    request: Request,
    status: int,
    detail: str | None = None,
    errors: list[dict[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    problema = Problema(
        title=_TITULOS.get(status, "Erro"),
        status=status,
        detail=detail,
        instance=request.url.path,
        errors=errors,
    )
    return JSONResponse(
        problema.model_dump(exclude_none=True),
        status_code=status,
        media_type=MEDIA_TYPE,
        headers=headers,
    )


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return resposta_problema(
            request, exc.status_code, str(exc.detail) if exc.detail else None, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, exc: RequestValidationError) -> JSONResponse:
        erros = [
            {"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return resposta_problema(request, 422, "Parâmetros inválidos.", errors=erros)

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception) -> JSONResponse:
        log.exception("api.erro_inesperado", path=request.url.path)
        return resposta_problema(request, 500)
