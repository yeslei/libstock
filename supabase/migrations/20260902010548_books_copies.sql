create table public.books (
    id bigint generated always as identity primary key,

    isbn varchar(17)
        unique,

    title varchar(255)
        not null,

    author varchar(255)
        not null,

    genre varchar(100),

    publication_year smallint,

    publisher varchar(150),

    edition varchar(50),

    cover_url text,

    is_active boolean
        not null default true,

    created_at timestamptz
        not null default now(),

    updated_at timestamptz
        not null default now(),

    constraint chk_book_publication_year
        check (
            publication_year is null
            or publication_year between 1000 and 2100
        )
);


create table public.copies (
    id bigint generated always as identity primary key,

    book_id bigint
        not null
        references public.books(id)
        on delete restrict,

    barcode varchar(100)
        not null unique,

    destination public.destination_type
        not null,

    status public.copy_status
        not null default 'AVAILABLE',

    condition varchar(30),

    sale_price numeric(10,2),

    acquired_at date,

    is_active boolean
        not null default true,

    created_at timestamptz
        not null default now(),

    updated_at timestamptz
        not null default now(),

    constraint chk_copy_sale_price
        check (
            sale_price is null
            or sale_price >= 0
        ),

    constraint chk_commercial_price
        check (
            destination <> 'COMMERCIAL'
            or sale_price is not null
        )
);