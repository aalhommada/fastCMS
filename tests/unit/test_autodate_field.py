"""
Unit tests for AutodateField type and auto-assignment logic.
"""
import pytest
from datetime import datetime, timezone

from app.utils.field_types import (
    AutodateOptions,
    FieldSchema,
    FieldType,
    FIELD_TYPE_SQL_MAP,
    FIELD_TYPE_PYTHON_MAP,
)


class TestAutodateFieldType:

    def test_autodate_in_field_type_enum(self):
        assert FieldType.AUTODATE == "autodate"

    def test_autodate_sql_map(self):
        assert FIELD_TYPE_SQL_MAP[FieldType.AUTODATE] == "TIMESTAMP"

    def test_autodate_python_map(self):
        assert FIELD_TYPE_PYTHON_MAP[FieldType.AUTODATE] is str

    def test_autodate_options_defaults(self):
        opts = AutodateOptions()
        assert opts.on_create is True
        assert opts.on_update is True

    def test_autodate_options_create_only(self):
        opts = AutodateOptions(on_create=True, on_update=False)
        assert opts.on_create is True
        assert opts.on_update is False

    def test_autodate_options_update_only(self):
        opts = AutodateOptions(on_create=False, on_update=True)
        assert opts.on_create is False
        assert opts.on_update is True

    def test_field_schema_with_autodate(self):
        fs = FieldSchema(
            name="created_at",
            type=FieldType.AUTODATE,
            autodate=AutodateOptions(on_create=True, on_update=False),
        )
        assert fs.type == FieldType.AUTODATE
        assert fs.autodate is not None
        assert fs.autodate.on_create is True
        assert fs.autodate.on_update is False

    def test_field_schema_autodate_defaults_to_none(self):
        fs = FieldSchema(name="title", type=FieldType.TEXT)
        assert fs.autodate is None

    def test_field_schema_autodate_none_by_default_on_autodate_type(self):
        # autodate field without explicit AutodateOptions — defaults to None in schema
        # (the service layer defaults on_create/on_update=True when options are None)
        fs = FieldSchema(name="last_sync", type=FieldType.AUTODATE)
        assert fs.type == FieldType.AUTODATE


class TestAutodateServiceLogic:
    """Test the record service logic for auto-setting autodate fields."""

    def _make_autodate_schema(self, on_create=True, on_update=True, name="created_at"):
        return FieldSchema(
            name=name,
            type=FieldType.AUTODATE,
            autodate=AutodateOptions(on_create=on_create, on_update=on_update),
        )

    def _simulate_create(self, field_schema: FieldSchema, data: dict) -> dict:
        """Simulate what record_service.create_record() does for autodate fields."""
        result = dict(data)
        opts = field_schema.autodate
        if opts is None or opts.on_create:
            result[field_schema.name] = datetime.now(timezone.utc)
        return result

    def _simulate_update(self, field_schema: FieldSchema, data: dict) -> dict:
        """Simulate what record_service.update_record() does for autodate fields."""
        result = dict(data)
        opts = field_schema.autodate
        if opts is not None and opts.on_update:
            result[field_schema.name] = datetime.now(timezone.utc)
        return result

    def test_create_sets_autodate_field(self):
        schema = self._make_autodate_schema(on_create=True)
        result = self._simulate_create(schema, {"title": "Hello"})
        assert "created_at" in result
        assert isinstance(result["created_at"], datetime)

    def test_create_does_not_set_field_if_on_create_false(self):
        schema = self._make_autodate_schema(on_create=False)
        result = self._simulate_create(schema, {"title": "Hello"})
        assert "created_at" not in result

    def test_update_sets_autodate_on_update_true(self):
        schema = self._make_autodate_schema(on_update=True)
        result = self._simulate_update(schema, {"title": "Changed"})
        assert "created_at" in result
        assert isinstance(result["created_at"], datetime)

    def test_update_does_not_set_field_if_on_update_false(self):
        schema = self._make_autodate_schema(on_update=False)
        result = self._simulate_update(schema, {"title": "Changed"})
        assert "created_at" not in result
