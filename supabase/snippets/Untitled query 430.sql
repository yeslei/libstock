select
    constraint_name,
    constraint_type
from information_schema.table_constraints
where table_name = 'sale_items';
