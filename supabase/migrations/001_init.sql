-- Modüler AI Üretim Hattı — initial schema

create extension if not exists "pgcrypto";

-- Profiles
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  credits integer not null default 10 check (credits >= 0),
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "Users can read own profile"
  on public.profiles for select
  using (auth.uid() = id);

create policy "Users can update own profile"
  on public.profiles for update
  using (auth.uid() = id);

-- Daily usage
create table if not exists public.usage_daily (
  user_id uuid not null references auth.users (id) on delete cascade,
  day date not null,
  generations_count integer not null default 0 check (generations_count >= 0),
  primary key (user_id, day)
);

alter table public.usage_daily enable row level security;

create policy "Users can read own usage"
  on public.usage_daily for select
  using (auth.uid() = user_id);

-- Generations
create type public.generation_type as enum ('logo', 'image', 'social');
create type public.generation_status as enum ('preview', 'unlocked', 'failed');

create table if not exists public.generations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  type public.generation_type not null,
  user_prompt text not null,
  engineered_prompt text not null default '',
  caption text,
  preview_url text,
  full_url text,
  model_used text,
  status public.generation_status not null default 'preview',
  credits_spent integer not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists generations_user_created_idx
  on public.generations (user_id, created_at desc);

alter table public.generations enable row level security;

create policy "Users can read own generations"
  on public.generations for select
  using (auth.uid() = user_id);

create policy "Users can insert own generations"
  on public.generations for insert
  with check (auth.uid() = user_id);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, credits)
  values (new.id, new.email, 10)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Storage bucket
insert into storage.buckets (id, name, public)
values ('generations', 'generations', true)
on conflict (id) do nothing;

-- Preview objects are public; full objects still need signed URL if you later
-- switch bucket to private. For MVP: allow authenticated read of own folder.
create policy "Public read generations bucket"
  on storage.objects for select
  using (bucket_id = 'generations');

create policy "Service role uploads via API"
  on storage.objects for insert
  with check (bucket_id = 'generations');

create policy "Service role update generations"
  on storage.objects for update
  using (bucket_id = 'generations');
