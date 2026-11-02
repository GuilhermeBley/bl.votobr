"""Aplicação FastAPI somente leitura, versionada em /api/v1 (seção 7). O OpenAPI é o contrato."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from votosbr import __version__
from votosbr.api.problemas import registrar_handlers
from votosbr.api.routers import meta, referencia, saude, votacoes
from votosbr.config import get_settings
from votosbr.logs import configurar_logs

PREFIXO = "/api/v1"


def create_app() -> FastAPI:
    cfg = get_settings()
    configurar_logs(json=cfg.log_json, nivel=cfg.log_nivel)
    app = FastAPI(
        title="VotosBR API",
        version=__version__,
        description="Como deputados federais e senadores votaram. Somente leitura.",
        openapi_url=f"{PREFIXO}/openapi.json",
        docs_url=f"{PREFIXO}/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.api_cors_origins,
        allow_methods=["GET", "HEAD", "OPTIONS"],
        allow_headers=["*"],
    )
    registrar_handlers(app)
    for router in (saude.router, meta.router, referencia.router, votacoes.router):
        app.include_router(router, prefix=PREFIXO)
    # Próximas tarefas: processos (T-402), parlamentares (T-403), busca (T-404),
    # Cache-Control/ETag e limite de requisições (T-405).
    return app


app = create_app()
