create type public.user_type as enum (
    'CLIENT',
    'EMPLOYEE'
);

create type public.notification_channel as enum (
    'EMAIL',
    'IN_APP'
);

create type public.destination_type as enum (
    'DIDACTIC',
    'COMMERCIAL'
);

create type public.copy_status as enum (
    'AVAILABLE',
    'BORROWED',
    'SOLD',
    'RESERVED',
    'INACTIVE'
);

create type public.loan_status as enum (
    'OPEN',
    'RETURNED',
    'CANCELLED'
);

create type public.sale_status as enum (
    'PENDING',
    'CONFIRMED',
    'CANCELLED'
);

create type public.reservation_status as enum (
    'WAITING',
    'NOTIFIED',
    'FULFILLED',
    'CANCELLED',
    'EXPIRED'
);

create type public.notification_status as enum (
    'PENDING',
    'SENT',
    'READ',
    'FAILED'
);