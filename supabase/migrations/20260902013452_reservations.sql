create table public.purchase_reservations (
    id bigint generated always as identity primary key,

    book_id bigint
        not null
        references public.books(id)
        on delete restrict,

    client_id uuid
        not null
        references public.clients(id)
        on delete restrict,

    fulfilled_copy_id bigint
        references public.copies(id)
        on delete restrict,

    requested_at timestamptz
        not null default now(),

    queue_position integer,

    status public.reservation_status
        not null default 'WAITING',

    notified_at timestamptz,

    expires_at timestamptz,

    created_at timestamptz
        not null default now(),

    constraint chk_reservation_queue_position
        check (
            queue_position is null
            or queue_position > 0
        ),

    constraint chk_reservation_expiration
        check (
            expires_at is null
            or expires_at > requested_at
        )
);

create unique index uq_active_reservation_client_book
on public.purchase_reservations(client_id, book_id)
where status in ('WAITING', 'NOTIFIED');