# Pendências — API e workers

Estado em 2026-11-02, depois da primeira etapa (estrutura de API e workers).
Referência: [votosbr-documento-base.md](../votosbr-documento-base.md).

## Decisões em aberto

- [ ] **Voto que some da fonte.** O loader faz upsert, mas não remove votos que deixaram de vir numa correção. A tabela `voto` não tem `removido_na_fonte_em` (seção 5.2 proíbe exclusão física). Opções: adicionar a coluna, ou tratar o conjunto de votos de uma votação como substituível (registrar na seção 13). Código: [loaders.py](../src/votosbr/etl/loaders.py) (`upsert_voto`) e [camara_votacoes.py](../src/votosbr/etl/jobs/camara_votacoes.py) (`_gravar`).
- [ ] **Votação que some da fonte.** Mesmo problema: `removido_na_fonte_em` existe em `votacao`, mas nada o preenche. É preciso definir quando considerar uma votação removida (por exemplo, quando ela não aparece mais na listagem da janela revisada).
- [ ] **Local do documento base.** A seção 8 prevê `docs/PROJETO.md`; hoje o arquivo está na raiz como `votosbr-documento-base.md`. Mover ou atualizar a seção 8.
- [ ] **ID inexistente responde 500 na Câmara.** O cliente trata 500 como erro transitório e tenta de novo até 5 vezes. Avaliar se vale tratar `/votacoes/{id}` com 500 persistente como "não encontrado".

## Workers (ingestão)

### Câmara
- [ ] **T-102 — completar o job de deputados.** Hoje ele só cria `pessoa` e `identificador_externo`. Falta montar `mandato`, `exercicio` e `filiacao` a partir de `/deputados/{id}/historico` ([camara_deputados.py](../src/votosbr/etl/jobs/camara_deputados.py)). Observação do fixture: o histórico mistura `idLegislatura` 56, 57 e 58, inclusive um registro com 58 datado de 2023-02-01. Investigar antes de modelar.
- [ ] **T-102 — rodar a 57ª legislatura inteira** e conferir que não há pessoa duplicada.
- [ ] **T-104 — backfill por arquivos em massa.** Só existe o esboço de URL em [bulk.py](../src/votosbr/sources/camara/bulk.py). Validar o padrão de URL antes de implementar.
- [ ] **T-105 — proposições sob demanda com detalhe.** Hoje a proposição é criada a partir do resumo embutido na votação; faltam `/proposicoes/{id}` (situação, inteiro teor, palavras-chave) e a reconsulta de proposições com votação nos últimos 30 dias.
- [ ] **T-107 — inferência de `NAO_REGISTROU`.** Depende de T-102 (exercício). O comando `votosbr derive nao-registrou` está criado, mas não implementado.
- [ ] **Coletar mais fixtures:** um PEC com turnos, uma votação com obstrução, um suplente, um deputado em licença e uma página de `/deputados` com `links[rel=next]`. O checklist 3.6 pede ao menos 3 casos por recurso.

### Senado
- [x] **T-201 — fixtures e schemas** de `/votacao` e `/senador/{codigo}` (decisão 013).
- [x] **T-203 — votações de Plenário** com checkpoint próprio (`senado-votacoes`), no `run diario`.
- [ ] **Orientação de bancada do Senado:** `/plenario/votacao/orientacaoBancada/{inicio}/{fim}` responde e também traz a hora da votação (hoje `data_hora` fica nulo no Senado). Ligar por `sequencialVotacao`.
- [ ] **Voto `NA` ("Dispositivo não citado")**: significado não confirmado; hoje vira `OUTRO` + `valor_nao_mapeado`.
- [ ] **Mensagens de autoridades (`MSF`, `OFS`)**: são a maioria das votações nominais do Senado (embaixadores, ministros do TCU etc.) e caem em objeto `OUTRO`/`TEXTO_BASE`. Avaliar um objeto próprio.
- [ ] **Mais fixtures do Senado:** votação rejeitada, PEC em 2º turno com placar, senador suplente.
- [ ] **T-202 — senadores** (mandatos de 8 anos, suplentes, filiações). Hoje a pessoa é criada sob demanda a partir de `/senador/{codigo}`, sem mandato.
- [ ] **T-204 — matérias e processos sob demanda.**
- [ ] **T-205 — resolução de pessoas entre Casas** + `curadoria/pessoas.yaml`.

### Domínio e qualidade
- [ ] **T-301/T-302 — processos legislativos e normas** (regras 6.6, LexML, troca de slug com `slug_alias`).
- [ ] **T-303 — classificação.** O objeto e a modalidade já são calculados na carga; falta a votação principal (`principal`, `principal_origem`) e o relatório de cobertura de `objeto = OUTRO`.
- [ ] **T-304 — temas:** o vocabulário oficial da Câmara (32 temas, `codTema`) já está em `seeds/temas.yaml`; falta ligar processos a temas (`processo_tema`), que depende de T-301.
- [ ] **T-305 — checks C01–C10** e a tabela `resultado_check`. Hoje C04 (sigla não resolvida) e C05 (valor não mapeado) só viram alertas no log da execução.
- [ ] **`votosbr reprocess`** (reconstruir a partir do RawStore, sem rede).

### Seeds
- [ ] **`seeds/partidos.yaml`** tem só as 22 siglas atuais vistas nos votos de out/2026. Faltam:
  - número eleitoral (TSE) e o nome do DC, que não aparece em `GET /partidos` da Câmara (os demais nomes vieram de lá);
  - histórico de renomeações, fusões e incorporações (PMDB→MDB, PR→PL, DEM+PSL→União, PTB+Patriota→PRD), necessário para o backfill;
  - o "PL" anterior a 2006 como partido distinto;
- [ ] A Câmara usa 3 ids de partido para "PP" (36763, 36845, 37903): entender o motivo.

### Operação
- [ ] **T-501 — `run diario` completo:** hoje ele roda só `camara-votacoes` e pula as outras etapas com aviso. Falta refresh condicional (ERRO bloqueia) e alertas (e-mail, Slack ou Telegram).
- [x] **Agendamento** às 06h (Brasília): o worker do Compose roda `votosbr run agendado`.
- [ ] Execuções extras em dia de sessão (hoje só há uma por dia, mais uma ao subir o worker).
- [ ] **T-502 — deploy:** container da API, job agendado, Postgres gerenciado com backup, RawStore em S3 (hoje é disco local).

## API

- [ ] **T-402 — processos:** `/processos`, `/processos/{slug}`, `/processos/{slug}/votacoes` e `/normas/{tipo}/{numero}/{ano}`, com redirecionamento 301 para slugs antigos.
- [ ] **T-403 — views materializadas** (`mv_placar_*`, `mv_parlamentar_metricas`, `mv_processo_resumo`), `refresh views` e os endpoints de parlamentares (`/parlamentares`, `/{slug}`, `/{slug}/votos`, `/{slug}/metricas`). Hoje o placar de `/votacoes/{id}` é calculado direto sobre `voto`.
- [ ] **T-404 — busca unificada** (`/busca`), mais os triggers de `tsvector` em `norma.busca` e `processo_legislativo.busca`.
- [ ] **T-405 — Cache-Control, ETag e limite de requisições por IP.**
- [ ] **`/votacoes/{id}/placar?agrupar=bancada`:** hoje só aceita `partido` e `uf`.
- [ ] **`/meta/atualizacao`:** `dados_desde` usa sempre `INGESTAO_DATA_INICIAL`; ajustar quando houver backfill.
- [ ] **Usuário somente leitura:** confirmar em ambiente fora do Docker que `DATABASE_URL_READONLY` está configurado. Sem ele, a API usa o usuário de escrita.

## Infra e qualidade de código

- [ ] **CI ainda não rodou de verdade:** o workflow em [.github/workflows/ci.yml](../.github/workflows/ci.yml) foi escrito, mas nunca executado.
- [ ] **`pre-commit install`** não foi rodado.
- [ ] **Aviso de depreciação:** `starlette.testclient` com `httpx` (sugere `httpx2`). Não quebra nada hoje.
- [ ] **Banco local:** o volume `pgdata` pode ter as 5 votações reais de 28/10/2026 (carga de teste). Use `docker compose down -v` para zerar.
