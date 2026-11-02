-- Executado só na criação do volume. Extensões e usuário somente leitura da API (seção 4).
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE ROLE votosbr_leitura LOGIN PASSWORD 'votosbr_leitura';
GRANT CONNECT ON DATABASE votosbr TO votosbr_leitura;
GRANT USAGE ON SCHEMA public TO votosbr_leitura;
-- Tabelas e views criadas depois pelo usuário de migração ficam legíveis automaticamente.
ALTER DEFAULT PRIVILEGES FOR ROLE votosbr IN SCHEMA public GRANT SELECT ON TABLES TO votosbr_leitura;
