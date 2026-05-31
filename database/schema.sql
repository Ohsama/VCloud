-- ============================================================
-- VCloud — Supabase Database Schema
-- Run this in the Supabase SQL Editor: supabase.com/dashboard
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── shops ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shops (
    id         UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
    name       TEXT        NOT NULL,
    location   TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ── camera_recordings ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS camera_recordings (
    id           UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
    shop_id      UUID        NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    camera_name  TEXT        NOT NULL,
    start_time   TIMESTAMPTZ NOT NULL,
    end_time     TIMESTAMPTZ NOT NULL,
    s3_video_url TEXT        NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- ── Indexes ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_recordings_shop_id
    ON camera_recordings(shop_id);

CREATE INDEX IF NOT EXISTS idx_recordings_start_time
    ON camera_recordings(start_time DESC);

-- ── Row-Level Security ───────────────────────────────────────
ALTER TABLE shops ENABLE ROW LEVEL SECURITY;
ALTER TABLE camera_recordings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read on shops"
    ON shops FOR SELECT USING (true);

CREATE POLICY "Allow public read on camera_recordings"
    ON camera_recordings FOR SELECT USING (true);

CREATE POLICY "Allow service insert on camera_recordings"
    ON camera_recordings FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow service insert on shops"
    ON shops FOR INSERT WITH CHECK (true);

-- ── Seed Data ────────────────────────────────────────────────
INSERT INTO shops (id, name, location)
VALUES ('00000000-0000-0000-0000-000000000001', 'Test Shop', 'Casablanca, Morocco')
ON CONFLICT (id) DO NOTHING;
