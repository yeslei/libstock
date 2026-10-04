"""Preenche o prazo de retirada das reservas NOTIFIED sem expires_at (Issue #150).

Reservas destinadas antes da política de prazo ficaram com expires_at NULL e nunca venceriam. O prazo é o da regra
`reservation_pickup_deadline`: último instante (23:59:59.999) do 5º dia corrido contado da data de negócio
(America/Sao_Paulo) de notified_at. Só toca reservas NOTIFIED com notified_at e sem expires_at.
"""
from alembic import op

revision = '20261003_0014'
down_revision = '20261003_0013'
branch_labels = None
depends_on = None


def upgrade():
    # O gatilho de validação rejeitaria o UPDATE de reservas de clientes hoje inativos ou penalizados: o backfill
    # não muda o estado da reserva, só preenche o prazo; a auditoria (trg_audit_purchase_reservation) continua ativa.
    op.execute('ALTER TABLE purchase_reservations DISABLE TRIGGER trg_validate_purchase_reservation')
    op.execute("""
        UPDATE purchase_reservations
        SET expires_at = ((notified_at AT TIME ZONE 'America/Sao_Paulo')::date + 6)::timestamp
                         AT TIME ZONE 'America/Sao_Paulo' - interval '1 millisecond'
        WHERE status = 'NOTIFIED' AND expires_at IS NULL AND notified_at IS NOT NULL
    """)
    op.execute('ALTER TABLE purchase_reservations ENABLE TRIGGER trg_validate_purchase_reservation')


def downgrade():
    # Intencionalmente sem desfazer: os prazos preenchidos são válidos pela regra aprovada, o código anterior os
    # tolera e não há marca que distinga o valor preenchido aqui de um prazo gravado pela aplicação.
    pass
