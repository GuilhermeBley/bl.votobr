from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from votosbr.api.deps import SessaoDep
from votosbr.api.schemas.referencia import Saude

router = APIRouter(tags=["meta"])


@router.get("/saude", response_model=Saude)
def saude(sessao: SessaoDep) -> Saude:
    try:
        sessao.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Banco de dados indisponível.") from exc
    return Saude(status="ok", banco="ok")
