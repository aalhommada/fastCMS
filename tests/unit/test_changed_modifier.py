"""
Unit tests for the :changed modifier in access control rule evaluation.
"""
import pytest

from app.core.access_control import AccessControlEngine, AccessContext


def _make_context(record_data: dict, old_record_data: dict | None = None) -> AccessContext:
    return AccessContext(
        record_data=record_data,
        old_record_data=old_record_data or {},
    )


class TestChangedModifier:

    def test_changed_returns_true_when_value_differs(self):
        ctx = _make_context(
            record_data={"status": "published"},
            old_record_data={"status": "draft"},
        )
        engine = AccessControlEngine()
        result = engine._replace_tokens("status:changed", ctx)
        assert result == "True"

    def test_changed_returns_false_when_value_same(self):
        ctx = _make_context(
            record_data={"status": "draft"},
            old_record_data={"status": "draft"},
        )
        engine = AccessControlEngine()
        result = engine._replace_tokens("status:changed", ctx)
        assert result == "False"

    def test_changed_returns_true_when_field_is_new(self):
        """A field that didn't exist before is considered changed."""
        ctx = _make_context(
            record_data={"new_field": "value"},
            old_record_data={},
        )
        engine = AccessControlEngine()
        result = engine._replace_tokens("new_field:changed", ctx)
        assert result == "True"

    def test_changed_returns_true_when_field_set_to_none(self):
        """Clearing a field (None) from a previous value is a change."""
        ctx = _make_context(
            record_data={"title": None},
            old_record_data={"title": "old title"},
        )
        engine = AccessControlEngine()
        result = engine._replace_tokens("title:changed", ctx)
        assert result == "True"

    def test_changed_in_full_rule_string(self):
        """Test :changed modifier inside a broader rule string."""
        ctx = _make_context(
            record_data={"role": "admin"},
            old_record_data={"role": "user"},
        )
        engine = AccessControlEngine()
        rule = "role:changed = True"
        result = engine._replace_tokens(rule, ctx)
        assert "True" in result

    def test_unchanged_field_in_rule(self):
        ctx = _make_context(
            record_data={"role": "user"},
            old_record_data={"role": "user"},
        )
        engine = AccessControlEngine()
        rule = "role:changed = True"
        result = engine._replace_tokens(rule, ctx)
        assert "False" in result

    def test_no_old_record_data_treats_all_as_changed(self):
        """When old_record_data is empty, all present fields are treated as changed."""
        ctx = _make_context(record_data={"title": "hello"})
        engine = AccessControlEngine()
        result = engine._replace_tokens("title:changed", ctx)
        assert result == "True"

    def test_changed_works_with_numeric_values(self):
        ctx = _make_context(
            record_data={"count": 10},
            old_record_data={"count": 10},
        )
        engine = AccessControlEngine()
        result = engine._replace_tokens("count:changed", ctx)
        assert result == "False"

    def test_changed_detects_numeric_update(self):
        ctx = _make_context(
            record_data={"count": 11},
            old_record_data={"count": 10},
        )
        engine = AccessControlEngine()
        result = engine._replace_tokens("count:changed", ctx)
        assert result == "True"
