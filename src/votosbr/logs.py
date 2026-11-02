"""Logs estruturados (structlog). Jobs vinculam `execucao_id` ao contexto (seção 6.9)."""

import logging
import sys

import structlog


def configurar_logs(json: bool = True, nivel: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=nivel)
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(nivel)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
