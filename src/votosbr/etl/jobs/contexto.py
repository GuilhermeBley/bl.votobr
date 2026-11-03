"""Montagem das dependências de um job (banco, RawStore, clientes, tabelas de normalização)."""

from dataclasses import dataclass, field
from functools import cached_property

from sqlalchemy.orm import Session, sessionmaker

from votosbr.config import Settings
from votosbr.domain.classificacao import ClassificadorObjeto
from votosbr.domain.normalizacao import Normalizador
from votosbr.etl.controle import Execucao, SqlCheckpointRepo, SqlRegistroRaw
from votosbr.sources.camara.client import CamaraClient, criar_http_camara
from votosbr.sources.http import HttpClient
from votosbr.sources.raw_store import RawStore
from votosbr.sources.senado.client import SenadoClient, criar_http_senado


@dataclass
class ContextoJob:
    settings: Settings
    fabrica: sessionmaker[Session]
    execucao: Execucao
    _clientes_http: list[HttpClient] = field(default_factory=list)

    @cached_property
    def raw_store(self) -> RawStore:
        return RawStore(
            self.settings.raw_store_path, SqlRegistroRaw(self.fabrica, self.execucao.id)
        )

    @cached_property
    def camara(self) -> CamaraClient:
        http = criar_http_camara(self.settings, self.raw_store)
        self._clientes_http.append(http)
        return CamaraClient(http)

    @cached_property
    def senado(self) -> SenadoClient:
        http = criar_http_senado(self.settings, self.raw_store)
        self._clientes_http.append(http)
        return SenadoClient(http)

    @cached_property
    def checkpoints(self) -> SqlCheckpointRepo:
        return SqlCheckpointRepo(self.fabrica)

    @cached_property
    def normalizador(self) -> Normalizador:
        return Normalizador.carregar(self.settings.dir_normalizacao)

    @cached_property
    def classificador(self) -> ClassificadorObjeto:
        return ClassificadorObjeto.de_yaml(self.settings.dir_normalizacao / "objeto_votacao.yaml")

    def fechar(self) -> None:
        for http in self._clientes_http:
            http.close()
