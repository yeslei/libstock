create or replace view public.book_availability as
select
    b.id as book_id,
    b.isbn,
    b.title,
    b.author,

    count(c.id) filter (
        where
            c.destination = 'COMMERCIAL'
            and c.status = 'AVAILABLE'
            and c.is_active = true
    ) as available_for_sale,

    count(c.id) filter (
        where
            c.destination = 'DIDACTIC'
            and c.status = 'AVAILABLE'
            and c.is_active = true
    ) as available_for_loan,

    count(c.id) filter (
        where
            c.status = 'BORROWED'
            and c.is_active = true
    ) as borrowed_count

from public.books b

left join public.copies c
    on c.book_id = b.id

where b.is_active = true

group by
    b.id,
    b.isbn,
    b.title,
    b.author;

create or replace view public.overdue_loans as
select
    l.id as loan_id,

    l.client_id,
    l.copy_id,

    l.loan_date,
    l.due_date,

    now() - l.due_date as overdue_duration

from public.loans l

where
    l.status = 'OPEN'
    and l.returned_at is null
    and l.due_date < now();