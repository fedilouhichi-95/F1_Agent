-- PitStop Assistant — schéma Supabase (PostgreSQL hébergé)
-- Exécuter dans l'éditeur SQL Supabase. Conçu MULTI-SAISON : la colonne
-- `season` est présente sur chaque table factuelle.
-- Les séquences d'identités et RLS seront activées avec le code du pipeline.

CREATE TABLE IF NOT EXISTS drivers (
    driver_id   INTEGER PRIMARY KEY REFERENCES drivers (driver_id),
    season      SMALLINT NOT NULL,
    name        TEXT NOT NULL,
    code        TEXT,
    number      INTEGER,
    nationality TEXT
);

-- TODO: le schéma complet (races, results, constructors, standings, laps,
-- pit_stops, tire_stints, logs) est figé avec la Phase 1 de la SPEC
-- (ingestion des données F1 2023). Ne pas créer de tables manuellement
-- en dehors de ce fichier et du code du pipeline.