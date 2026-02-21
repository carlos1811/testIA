-- Script SQL para crear las tablas usadas por la aplicación
-- Generated: 2026-02-21

-- Recomendación: ejecutar esto en la base de datos indicada por DATABASE_URL.
-- Ejemplo (PowerShell):
-- psql "postgres://user:password@host:5432/dbname" -f .\sql\create_tables.sql

-- Crear extensión para generar UUIDs (usa pgcrypto -> gen_random_uuid).
-- Si prefieres uuid-ossp, sustituye por: CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Tabla: users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tabla: matches
CREATE TABLE IF NOT EXISTS matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_a_id UUID NOT NULL,
    user_b_id UUID NOT NULL,
    compatibility_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'suggested',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_matches_user_a FOREIGN KEY (user_a_id) REFERENCES users(id),
    CONSTRAINT fk_matches_user_b FOREIGN KEY (user_b_id) REFERENCES users(id)
);

-- Tabla: psychological_profiles
CREATE TABLE IF NOT EXISTS psychological_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    summary_text TEXT NOT NULL DEFAULT '',
    writing_style_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    empathy_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    openness_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_profile_user FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Trigger para actualizar `updated_at` en psychological_profiles al actualizar la fila
CREATE OR REPLACE FUNCTION set_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_updated_at ON psychological_profiles;
CREATE TRIGGER trg_set_updated_at
BEFORE UPDATE ON psychological_profiles
FOR EACH ROW
EXECUTE FUNCTION set_updated_at_column();

-- Índices adicionales (opcionales)
-- CREATE INDEX IF NOT EXISTS idx_matches_user_a ON matches(user_a_id);
-- CREATE INDEX IF NOT EXISTS idx_matches_user_b ON matches(user_b_id);
-- CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON psychological_profiles(user_id);

-- Fin del script
