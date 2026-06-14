-- ================================================================
-- Heryah Finance Superhero — Supabase Setup SQL
-- Run this once in Supabase: Project > SQL Editor > New query
-- ================================================================

-- 1. EXTENSIONS ------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. ENUM TYPES ------------------------------------------------
CREATE TYPE transaction_type AS ENUM ('expense', 'income');

-- 3. TABLES ----------------------------------------------------

-- One row per Telegram user
CREATE TABLE IF NOT EXISTS public.users (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id   BIGINT      UNIQUE NOT NULL,
    username      TEXT,
    first_name    TEXT,
    last_name     TEXT,
    budget_day    SMALLINT    NOT NULL DEFAULT 25
                              CHECK (budget_day BETWEEN 1 AND 31),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Expense / income labels, one set per user
CREATE TABLE IF NOT EXISTS public.categories (
    id          UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID             NOT NULL
                                 REFERENCES public.users(id) ON DELETE CASCADE,
    name        TEXT             NOT NULL,
    type        transaction_type NOT NULL,
    created_at  TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, name, type)
);

-- Monthly budget per category per user
CREATE TABLE IF NOT EXISTS public.budgets (
    id          UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID           NOT NULL
                               REFERENCES public.users(id) ON DELETE CASCADE,
    category_id UUID           NOT NULL
                               REFERENCES public.categories(id) ON DELETE CASCADE,
    amount      NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, category_id)
);

-- All money movements (replaces the separate expenses + income tables)
CREATE TABLE IF NOT EXISTS public.transactions (
    id             UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID             NOT NULL
                                    REFERENCES public.users(id) ON DELETE CASCADE,
    category_id    UUID             NOT NULL
                                    REFERENCES public.categories(id),
    amount         NUMERIC(12, 2)   NOT NULL CHECK (amount > 0),
    type           transaction_type NOT NULL,
    transacted_at  TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    created_at     TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

-- 4. INDEXES ---------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_users_telegram_id
    ON public.users (telegram_id);

CREATE INDEX IF NOT EXISTS idx_categories_user_type
    ON public.categories (user_id, type);

CREATE INDEX IF NOT EXISTS idx_budgets_user_category
    ON public.budgets (user_id, category_id);

CREATE INDEX IF NOT EXISTS idx_transactions_user_period
    ON public.transactions (user_id, transacted_at DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_category
    ON public.transactions (category_id);

-- 5. AUTO-UPDATE updated_at ------------------------------------

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_users_updated_at   ON public.users;
DROP TRIGGER IF EXISTS trg_budgets_updated_at ON public.budgets;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_budgets_updated_at
    BEFORE UPDATE ON public.budgets
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- 6. ROW LEVEL SECURITY ----------------------------------------
--
-- The bot uses the service_role key, which bypasses RLS entirely.
-- RLS is still enabled so that the anon key and any JWT-authenticated
-- access cannot read or write data directly (defense-in-depth).
--
-- To grant a specific Telegram user read access via JWT in future,
-- add policies here that check `auth.uid()` or a custom claim.

ALTER TABLE public.users        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.budgets      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;

-- Deny all anon access
CREATE POLICY "deny_anon_users"
    ON public.users FOR ALL TO anon USING (false);

CREATE POLICY "deny_anon_categories"
    ON public.categories FOR ALL TO anon USING (false);

CREATE POLICY "deny_anon_budgets"
    ON public.budgets FOR ALL TO anon USING (false);

CREATE POLICY "deny_anon_transactions"
    ON public.transactions FOR ALL TO anon USING (false);

-- Deny all authenticated JWT access (update these if you add a web UI)
CREATE POLICY "deny_auth_users"
    ON public.users FOR ALL TO authenticated USING (false);

CREATE POLICY "deny_auth_categories"
    ON public.categories FOR ALL TO authenticated USING (false);

CREATE POLICY "deny_auth_budgets"
    ON public.budgets FOR ALL TO authenticated USING (false);

CREATE POLICY "deny_auth_transactions"
    ON public.transactions FOR ALL TO authenticated USING (false);

-- ================================================================
-- DONE — copy your Supabase project URL and service_role key
-- into your .env file and run the bot.
-- ================================================================
