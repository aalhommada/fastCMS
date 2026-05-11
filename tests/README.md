# FastCMS Tests

This directory contains automated tests for FastCMS.

## Test Structure

```
tests/
├── e2e/              # End-to-end tests
├── integration/       # Integration tests
├── unit/             # Unit tests
├── conftest.py       # Pytest fixtures
└── README.md         # This file
```

## Running Tests

### Run all tests
```bash
.venv/bin/pytest
```

### Run only e2e tests
```bash
.venv/bin/pytest tests/e2e/
```

### Run a specific test file
```bash
.venv/bin/pytest tests/e2e/test_fastcms_core.py
```

### Run with coverage
```bash
.venv/bin/pytest --cov=app --cov-report=html
```

## Test Categories

### E2E Tests (`tests/e2e/`)
End-to-end tests that test the entire application through the API:
- `test_fastcms_core.py` - Core features (auth, collections, records, access control)
- `test_email_verification.py` - Email verification and password reset flows

### Integration Tests (`tests/integration/`)
Tests that verify multiple components working together.

### Unit Tests (`tests/unit/`)
Tests for individual functions and classes.

## Writing Tests

### Example E2E Test
```python
async def test_create_collection(self, client: AsyncClient):
    # Register and login
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        },
    )
    token = response.json()["token"]["access_token"]

    # Create collection
    response = await client.post(
        "/api/v1/collections",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "posts",
            "type": "base",
            "schema": [
                {"name": "title", "type": "text", "validation": {}},
            ],
        },
    )
    assert response.status_code == 201
```

## Test Database

Tests use an in-memory SQLite database that is created and destroyed for each test session.

## Dependencies

All test dependencies are in `requirements.txt`:
- pytest
- pytest-asyncio
- pytest-cov
- httpx

Install the dev environment (test deps included) with:
```bash
uv sync --all-extras
```
