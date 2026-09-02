create table public.audit_logs (
    id bigint generated always as identity primary key,

    employee_id uuid
        references public.employees(id)
        on delete restrict,

    entity_type varchar(100)
        not null,

    entity_id varchar(100)
        not null,

    operation varchar(100)
        not null,

    old_value jsonb,

    new_value jsonb,

    occurred_at timestamptz
        not null default now()
);

create or replace function public.prevent_audit_log_modification()
returns trigger
language plpgsql
as $$
begin
    raise exception 'Audit logs cannot be modified or deleted';
end;
$$;

create trigger trg_prevent_audit_log_modification
before update or delete
on public.audit_logs
for each row
execute function public.prevent_audit_log_modification();