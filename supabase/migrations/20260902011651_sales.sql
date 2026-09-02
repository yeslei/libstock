create table public.sales (
    id bigint generated always as identity primary key,

    client_id uuid
        references public.clients(id)
        on delete restrict,

    employee_id uuid
        not null
        references public.employees(id)
        on delete restrict,

    sale_date timestamptz
        not null default now(),

    total_amount numeric(12,2)
        not null default 0,

    status public.sale_status
        not null default 'PENDING',

    created_at timestamptz
        not null default now(),

    constraint chk_sale_total
        check (total_amount >= 0)
);


create table public.sale_items (
    id bigint generated always as identity primary key,

    sale_id bigint
        not null
        references public.sales(id)
        on delete restrict,

    copy_id bigint
        not null
        references public.copies(id)
        on delete restrict,

    unit_price numeric(10,2)
        not null,

    created_at timestamptz
        not null default now(),

    constraint uq_sale_item_copy
        unique (copy_id),

    constraint chk_sale_item_price
        check (unit_price >= 0)
);

create index idx_sales_employee
on public.sales(employee_id);

create index idx_sales_client
on public.sales(client_id);

create index idx_sale_items_sale
on public.sale_items(sale_id);