"""Validate migrations and tests in a disposable LOCAL PostgreSQL database."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql

backend = Path(__file__).resolve().parents[1]
database_name = 'libstock_v2_check_' + uuid4().hex[:12]
admin = psycopg.connect('host=127.0.0.1 port=54322 dbname=postgres user=postgres password=postgres', autocommit=True)
admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database_name)))
environment = dict(os.environ)
environment['DATABASE_URL'] = f'postgresql+psycopg://postgres:postgres@127.0.0.1:54322/{database_name}'
environment['LIBSTOCK_V2_TEST_DATABASE_URL'] = environment['DATABASE_URL']
try:
    for arguments in [
        ['-m', 'alembic', 'upgrade', 'head'],
        ['-m', 'alembic', 'check'],
        ['-m', 'alembic', 'downgrade', '-1'],
        ['-m', 'alembic', 'upgrade', 'head'],
        ['-m', 'pytest', '-q'],
    ]:
        if arguments[1] == 'pytest':
            # Existing integration tests require an employee in the migrated DB.
            with psycopg.connect(host='127.0.0.1', port=54322, dbname=database_name,
                                 user='postgres', password='postgres') as seed:
                role_id = seed.execute("SELECT id FROM roles WHERE code = 'ADMINISTRATOR'").fetchone()[0]
                user_id = seed.execute("INSERT INTO users (name, email, password_hash) VALUES ('Teste Admin', 'seed@test.invalid', 'test') RETURNING id").fetchone()[0]
                seed.execute('INSERT INTO profiles (id) VALUES (%s)', (user_id,))
                seed.execute('INSERT INTO employees (id, employee_code, role_id) VALUES (%s, %s, %s)', (user_id, 'TEST-SEED', role_id))
                seed.execute('INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)', (user_id, role_id))
        subprocess.run([sys.executable, *arguments], cwd=backend, env=environment, check=True)
finally:
    admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database_name)))
    admin.close()
