create table public.profiles (
    id uuid primary key
        references auth.users(id)
        on delete cascade,

    name varchar(150) not null,

    phone varchar(30),

    user_type public.user_type not null,

    notification_preference public.notification_channel
        not null default 'IN_APP',

    is_active boolean
        not null default true,

    created_at timestamptz
        not null default now(),

    updated_at timestamptz
        not null default now()
);