create table public.roles (
    id bigint generated always as identity primary key,

    name varchar(50)
        not null unique,

    description varchar(255)
);


create table public.clients (
    id uuid primary key
        references public.profiles(id)
        on delete cascade,

    registration_number varchar(50)
        unique,

    is_penalized boolean
        not null default false,

    created_at timestamptz
        not null default now()
);


create table public.employees (
    id uuid primary key
        references public.profiles(id)
        on delete cascade,

    employee_code varchar(50)
        not null unique,

    role_id bigint
        not null
        references public.roles(id)
        on delete restrict,

    created_at timestamptz
        not null default now()
);