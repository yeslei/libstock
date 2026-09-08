import importlib.util
from pathlib import Path
from types import SimpleNamespace

from app.models.domain import Copy, DestinationType


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260908_0010_remove_destination_tags.py"
)


def load_migration():
    spec = importlib.util.spec_from_file_location("remove_destination_tags", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeOperations:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def __getattr__(self, name: str):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record


def test_modelo_mantem_apenas_destinacao_operacional() -> None:
    assert "destination" in Copy.__table__.columns
    assert "destination_tag_id" not in Copy.__table__.columns
    assert {item.value for item in DestinationType} == {"DIDACTIC", "COMMERCIAL"}


def test_upgrade_remove_coluna_e_tabela_de_tags() -> None:
    migration = load_migration()
    operations = FakeOperations()
    migration.op = operations

    migration.upgrade()

    assert [call[0] for call in operations.calls] == [
        "drop_index",
        "drop_constraint",
        "drop_column",
        "drop_table",
    ]
    assert operations.calls[2][1] == ("copies", "destination_tag_id")
    assert operations.calls[3][1] == ("destination_tags",)


def test_downgrade_recria_estrutura_removida() -> None:
    migration = load_migration()
    operations = FakeOperations()
    migration.op = operations

    migration.downgrade()

    assert [call[0] for call in operations.calls] == [
        "create_table",
        "execute",
        "add_column",
        "create_foreign_key",
        "create_index",
    ]
    assert operations.calls[0][1][0] == "destination_tags"
    assert operations.calls[2][1][0] == "copies"
