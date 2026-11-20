-- FinSight AI — Supabase Row Level Security policies
-- Supabase-only: relies on auth.uid(), which only exists inside
-- Supabase's Postgres (it comes from the Supabase Auth extension).
-- Apply this AFTER schema.sql, and only against a real Supabase
-- project — do not run this against the local docker-compose
-- Postgres, which has no auth.uid() function.
--
-- Run via the Supabase SQL editor, or:
--   supabase db execute --file infra/supabase/rls_policies.sql

-- ---------------------------------------------------------------------
-- Row Level Security — every table is tenant-scoped by business_id.
-- Adjust the `owner_user_id` join if you model team members
-- (many-to-many business <-> user) instead of single ownership.
-- ---------------------------------------------------------------------
alter table businesses enable row level security;
alter table documents enable row level security;
alter table document_chunks enable row level security;
alter table financial_records enable row level security;
alter table chat_messages enable row level security;
alter table reports enable row level security;

create policy "owner can read own business" on businesses
    for select using (auth.uid() = owner_user_id);

create policy "owner can manage own business documents" on documents
    for all using (
        business_id in (select id from businesses where owner_user_id = auth.uid())
    );

create policy "owner can manage own business chunks" on document_chunks
    for all using (
        document_id in (
            select d.id from documents d
            join businesses b on b.id = d.business_id
            where b.owner_user_id = auth.uid()
        )
    );

create policy "owner can manage own financial records" on financial_records
    for all using (
        business_id in (select id from businesses where owner_user_id = auth.uid())
    );

create policy "owner can manage own chat messages" on chat_messages
    for all using (
        business_id in (select id from businesses where owner_user_id = auth.uid())
    );

create policy "owner can manage own reports" on reports
    for all using (
        business_id in (select id from businesses where owner_user_id = auth.uid())
    );
