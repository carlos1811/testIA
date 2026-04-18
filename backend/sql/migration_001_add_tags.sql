-- migration_001_add_tags.sql
-- Añade las tablas necesarias para el sistema de tags y matching por personalidad.
--
-- Cómo usarlo:
--   1. Base de datos NUEVA:
--        psql "postgres://user:password@host:5432/dbname" -f .\sql\create_tables.sql
--        psql "postgres://user:password@host:5432/dbname" -f .\sql\migration_001_add_tags.sql
--
--   2. Base de datos ACTIVA (ya tiene las tablas del create_tables.sql):
--        psql "postgres://user:password@host:5432/dbname" -f .\sql\migration_001_add_tags.sql

BEGIN;

-- -----------------------------------------------------------------------
-- 1. Catálogo de tags de personalidad extraídos por la IA
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(100) NOT NULL UNIQUE,
    category     VARCHAR(50),                    -- ej: 'emocion', 'valor', 'autoconocimiento'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------
-- 2. Relación N:M usuario <-> tags (con peso asignado por la IA)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_tags (
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tag_id       UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    weight       NUMERIC(5,2) NOT NULL DEFAULT 1.0,   -- relevancia del tag para el usuario
    source       VARCHAR(30)  NOT NULL DEFAULT 'ai',  -- origen: 'ai', 'manual', etc.
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, tag_id)
);

-- -----------------------------------------------------------------------
-- 3. Índices de rendimiento
-- -----------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_user_tags_tag_id  ON user_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_user_tags_user_id ON user_tags(user_id);

-- -----------------------------------------------------------------------
-- 4. Trigger para actualizar updated_at en user_tags
--    (reutiliza la función set_updated_at_column creada en create_tables.sql)
-- -----------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_user_tags_updated_at ON user_tags;
CREATE TRIGGER trg_user_tags_updated_at
    BEFORE UPDATE ON user_tags
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_column();

COMMIT;

