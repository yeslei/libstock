create table public.notifications (
    id bigint generated always as identity primary key,

    user_id uuid
        not null
        references public.profiles(id)
        on delete restrict,

    type varchar(50)
        not null,

    channel public.notification_channel
        not null,

    subject varchar(255),

    message text
        not null,

    status public.notification_status
        not null default 'PENDING',

    created_at timestamptz
        not null default now(),

    sent_at timestamptz,

    read_at timestamptz
);