# VotosBR — backend

Ingestão de votações do Congresso (workers) e API REST somente leitura para o frontend React.
Referência do projeto: [votosbr-documento-base.md](votosbr-documento-base.md).

## Rodando localmente

```bash
cp .env.example .env
uv sync
docker compose up -d db          # Postgres 16 com unaccent, pg_trgm e usuário somente leitura
uv run alembic upgrade head
uv run votosbr seed
```

**API** (`http://localhost:8000/api/v1/docs`; contrato em `/api/v1/openapi.json`):

```bash
uv run uvicorn votosbr.api.main:app --reload
```

**Workers** (CLI `votosbr`, um processo por execução, agendado por cron/systemd/CI):

```bash
uv run votosbr ingest camara-votacoes --dry-run      # mostra a janela calculada pelo checkpoint
uv run votosbr ingest camara-votacoes                # incremental (seção 6.2.1)
uv run votosbr ingest camara-votacoes --desde 2026-10-01 --ate 2026-10-31   # manual, não move o checkpoint
uv run votosbr checkpoint mostrar
uv run votosbr run diario                            # orquestração diária (06h Brasília)
```

Tudo em containers: `docker compose up api` e `docker compose run --rm worker` (perfil `worker`).

## Qualidade

```bash
uv run pytest            # integração usa TEST_DATABASE_URL (padrão: votosbr_test no Postgres local); pula se indisponível
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy src
```

Testes nunca acessam a rede: as fontes são simuladas com `respx` a partir de `tests/fixtures/`
(respostas reais coletadas em 2026-11-01).

## Estado das tarefas

| Tarefa | Situação |
|---|---|
| T-001 / T-002 | Repositório, Docker Compose, CI |
| T-003 | Cliente HTTP (retry, rate limit, paginação) + RawStore |
| T-004 | Modelo core (migração `0001`) + `votosbr seed` |
| T-101 | Fixtures e schemas da Câmara (votações, votos, orientações, deputado, histórico) |
| T-102 | **Parcial**: pessoas; falta mandato/exercício/filiação a partir do histórico |
| T-103 | Incremental de votações da Câmara com checkpoint |
| T-106 | Normalização via YAML + `valor_nao_mapeado` |
| T-401 | Esqueleto da API: envelope, problem details, CORS, OpenAPI, sessão somente leitura |
| T-402 | **Parcial**: votações, votos (+CSV, avisos), placar; faltam processos |
| Demais | Comandos já existem na CLI e respondem "ainda não implementado (T-xxx)" |
