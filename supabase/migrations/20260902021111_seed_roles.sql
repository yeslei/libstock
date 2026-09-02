insert into public.roles (
    name,
    description
)
values
    ('ATTENDANT', 'Atendente responsável pelas operações de balcão'),
    ('STOCK_KEEPER', 'Responsável pela organização e manutenção do acervo'),
    ('MANAGER', 'Gerente autorizado a executar operações críticas'),
    ('ADMINISTRATOR', 'Administrador do sistema')
on conflict (name) do nothing;