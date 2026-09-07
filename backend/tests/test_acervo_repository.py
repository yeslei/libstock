from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.domain import Book, Copy, DestinationTag, DestinationType, Employee, Profile, Role, UserRole
from app.models.user import User
from app.repositories.acervo_repository import AcervoRepository


class TestAcervoRepositoryIntegration:
    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:")
        # Cria apenas as tabelas necessárias para os testes do repositório
        for table in (
            User.__table__,
            Profile.__table__,
            Role.__table__,
            UserRole.__table__,
            Employee.__table__,
            Book.__table__,
            DestinationTag.__table__,
            Copy.__table__,
        ):
            table.create(self.engine)

        self.db = Session(self.engine)

        # Inserção de dados de apoio
        user = User(id=1, email="stock@libstock.com.br", password_hash="hash", name="Estoquista")
        profile = Profile(id=1)
        role = Role(id=1, code="STOCK_KEEPER", name="Estoquista")
        employee = Employee(id=1, employee_code="EMP-01", role_id=1)
        book = Book(id=1, title="Livro Teste", author="Autor Teste")

        tag_doacao = DestinationTag(id=1, name="Doação", slug="doacao", description="Para doação")
        tag_descarte = DestinationTag(id=2, name="Descarte", slug="descarte", description="Para descarte")

        copy = Copy(
            id=1,
            book_id=1,
            barcode="BC-001",
            destination=DestinationType.DIDACTIC,
            destination_tag_id=None,
        )

        self.db.add_all([user, profile, role, employee, book, tag_doacao, tag_descarte, copy])
        self.db.commit()

        self.repository = AcervoRepository(self.db)

    def teardown_method(self):
        self.db.close()
        self.engine.dispose()

    def test_find_item_by_id_and_destination_tag_relation(self):
        item = self.repository.find_item_by_id(1)
        assert item is not None
        assert item.id == 1
        assert item.destination_tag is None

    def test_find_tag_by_id_and_slug(self):
        tag_by_id = self.repository.find_tag_by_id(1)
        assert tag_by_id is not None
        assert tag_by_id.name == "Doação"

        tag_by_slug = self.repository.find_tag_by_name_or_slug("descarte")
        assert tag_by_slug is not None
        assert tag_by_slug.id == 2

        tag_by_name = self.repository.find_tag_by_name_or_slug("Doação")
        assert tag_by_name is not None
        assert tag_by_name.id == 1

        tag_nonexistent = self.repository.find_tag_by_name_or_slug("inexistente")
        assert tag_nonexistent is None

    def test_list_tags(self):
        tags = self.repository.list_tags()
        assert len(tags) == 2
        # Ordenado por nome ascendente: Descarte antes de Doação
        assert tags[0].slug == "descarte"
        assert tags[1].slug == "doacao"

    def test_assign_tag_to_item(self):
        item = self.repository.find_item_by_id(1)
        tag = self.repository.find_tag_by_id(1)

        updated_item = self.repository.assign_tag(item, tag)
        self.db.commit()

        reloaded = self.repository.find_item_by_id(1)
        assert reloaded is not None
        assert reloaded.destination_tag_id == 1
        assert reloaded.destination_tag.name == "Doação"

    def test_is_employee(self):
        assert self.repository.is_employee(1) is True
        assert self.repository.is_employee(999) is False

