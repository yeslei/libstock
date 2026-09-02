-- Catálogo

create index idx_books_title
on public.books(title);

create index idx_books_author
on public.books(author);


-- Exemplares

create index idx_copies_book
on public.copies(book_id);

create index idx_copies_book_status
on public.copies(book_id, status);

create index idx_copies_destination_status
on public.copies(destination, status);


-- Vendas

create index idx_sales_date
on public.sales(sale_date);


-- Reservas

create index idx_reservations_book_status
on public.purchase_reservations(book_id, status);

create index idx_reservations_client
on public.purchase_reservations(client_id);


-- Notificações

create index idx_notifications_user_status
on public.notifications(user_id, status);


-- Auditoria

create index idx_audit_entity
on public.audit_logs(entity_type, entity_id);

create index idx_audit_employee
on public.audit_logs(employee_id);

create index idx_audit_occurred_at
on public.audit_logs(occurred_at);