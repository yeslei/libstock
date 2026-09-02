create table public.loans (
    id bigint generated always as identity primary key,

    copy_id bigint
        not null
        references public.copies(id)
        on delete restrict,

    client_id uuid
        not null
        references public.clients(id)
        on delete restrict,

    employee_id uuid
        not null
        references public.employees(id)
        on delete restrict,

    loan_date timestamptz
        not null default now(),

    due_date timestamptz
        not null,

    returned_at timestamptz,

    status public.loan_status
        not null default 'OPEN',

    created_at timestamptz
        not null default now(),

    constraint chk_loan_due_date
        check (due_date > loan_date),

    constraint chk_loan_return_date
        check (
            returned_at is null
            or returned_at >= loan_date
        )
);

create unique index uq_loans_open_copy
on public.loans(copy_id)
where status = 'OPEN';

create index idx_loans_client_status
on public.loans(client_id, status);

create index idx_loans_due_date
on public.loans(due_date);