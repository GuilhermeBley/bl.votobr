"""RawStore: toda resposta original é gravada antes do parse (seções 0.2.6 e 6.1).

Caminho: `<raiz>/<fonte>/<recurso>/<AAAA>/<MM>/<sha256>.<ext>.gz`. Conteúdo idêntico é gravado
uma vez só (endereçado por hash); cada coleta gera um registro próprio em `raw_documento`.
"""

import gzip
import hashlib
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from votosbr.domain.enums import FonteDado


class RegistroRaw(Protocol):
    """Persiste os metadados de um documento bruto e devolve o id de `raw_documento`."""

    def registrar(
        self,
        *,
        fonte: FonteDado,
        url: str,
        parametros: Mapping[str, Any] | None,
        http_status: int,
        conteudo_hash: str,
        caminho_storage: str,
    ) -> int: ...


class RawStore:
    def __init__(self, raiz: Path, registro: RegistroRaw | None = None) -> None:
        self.raiz = raiz
        self.registro = registro

    def gravar(
        self,
        *,
        fonte: FonteDado,
        recurso: str,
        url: str,
        parametros: Mapping[str, Any] | None,
        http_status: int,
        corpo: bytes,
        content_type: str,
        agora: datetime | None = None,
    ) -> int | None:
        agora = agora or datetime.now(UTC)
        conteudo_hash = hashlib.sha256(corpo).hexdigest()
        extensao = "xml" if "xml" in content_type else "json"
        relativo = (
            Path(fonte.value.lower())
            / recurso
            / f"{agora:%Y}"
            / f"{agora:%m}"
            / f"{conteudo_hash}.{extensao}.gz"
        )
        destino = self.raiz / relativo
        if not destino.exists():
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporario = destino.with_suffix(f".{os.getpid()}.tmp")
            temporario.write_bytes(gzip.compress(corpo))
            temporario.replace(destino)

        if self.registro is None:
            return None
        return self.registro.registrar(
            fonte=fonte,
            url=url,
            parametros=dict(parametros) if parametros else None,
            http_status=http_status,
            conteudo_hash=conteudo_hash,
            caminho_storage=relativo.as_posix(),
        )

    def ler(self, caminho_storage: str) -> bytes:
        return gzip.decompress((self.raiz / caminho_storage).read_bytes())
