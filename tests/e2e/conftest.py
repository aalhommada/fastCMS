"""
E2E test configuration.

Disables rate limiting globally for all e2e tests so login calls
don't exhaust per-minute limits across the test suite.
"""

import pytest
from unittest.mock import patch, MagicMock

import app.core.rate_limit as _rl_module


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting for every e2e test."""
    original = _rl_module.settings
    mock_settings = MagicMock(wraps=original)
    mock_settings.RATE_LIMIT_ENABLED = False
    with patch.object(_rl_module, "settings", mock_settings):
        yield
