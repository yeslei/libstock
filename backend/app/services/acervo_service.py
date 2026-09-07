from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AcervoItemNotFoundError,
    AcervoPersistenceError,
    ApplicationError,
    AuditActorRequiredError,
    DestinationTagNotFoundError,
)
from app.models.domain import Copy, DestinationTag
from app.repositories.acervo_repository import AcervoRepository
from app.schemas.acervo_schema import ClassifyItemInput


class AcervoService:
    """Regras de negócio e controle transacional para classificação do acervo."""

    def __init__(
        self,
        db: Session,
        acervo_repository: AcervoRepository,
    ) -> None:
        self.db = db
        self.repository = acervo_repository

    def classify_item(
        self,
        item_id: int,
        payload: ClassifyItemInput,
        *,
        actor_id: int,
    ) -> Copy:
        try:
            if not self.repository.is_employee(actor_id):
                raise AuditActorRequiredError()

            item = self.repository.find_item_by_id(item_id)
            if item is None:
                raise AcervoItemNotFoundError()

            tag: DestinationTag | None = None
            if payload.tag_id is not None:
                tag = self.repository.find_tag_by_id(payload.tag_id)
            elif payload.tag_name is not None:
                tag = self.repository.find_tag_by_name_or_slug(payload.tag_name)

            if tag is None:
                raise DestinationTagNotFoundError()

            self.repository.set_audit_actor(actor_id)
            updated_item = self.repository.assign_tag(item, tag)
            self.db.commit()
            self.db.refresh(updated_item)
            return updated_item
        except ApplicationError:
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise AcervoPersistenceError() from exc
        except Exception as exc:
            self.db.rollback()
            raise AcervoPersistenceError() from exc

    def list_tags(self) -> list[DestinationTag]:
        return self.repository.list_tags()

    def get_item(self, item_id: int) -> Copy:
        item = self.repository.find_item_by_id(item_id)
        if item is None:
            raise AcervoItemNotFoundError()
        return item

