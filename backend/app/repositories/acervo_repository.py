from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.models.domain import Copy, DestinationTag, Employee


class AcervoRepository:
    """Repositório para persistência e consultas de itens do acervo e tags de destinação."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def find_item_by_id(self, item_id: int) -> Copy | None:
        statement = (
            select(Copy)
            .options(selectinload(Copy.destination_tag))
            .where(Copy.id == item_id)
        )
        return self.db.scalar(statement)

    def find_tag_by_id(self, tag_id: int) -> DestinationTag | None:
        return self.db.get(DestinationTag, tag_id)

    def find_tag_by_name_or_slug(self, name_or_slug: str) -> DestinationTag | None:
        normalized = name_or_slug.strip().lower()
        statement = select(DestinationTag).where(
            (func.lower(DestinationTag.name) == normalized)
            | (func.lower(DestinationTag.slug) == normalized)
        )
        return self.db.scalar(statement)

    def list_tags(self) -> list[DestinationTag]:
        statement = select(DestinationTag).order_by(DestinationTag.name.asc())
        return list(self.db.scalars(statement))

    def assign_tag(self, item: Copy, tag: DestinationTag) -> Copy:
        item.destination_tag_id = tag.id
        item.destination_tag = tag
        self.db.flush()
        return item

    def is_employee(self, user_id: int) -> bool:
        return self.db.scalar(select(Employee.id).where(Employee.id == user_id)) is not None

    def set_audit_actor(self, employee_id: int) -> None:
        """Configura o ator da transação para auditoria de inventário."""
        self.db.execute(
            text("SELECT set_config('libstock.employee_id', :valor, true)"),
            {"valor": str(employee_id)},
        )

