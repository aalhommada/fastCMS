"""
Test script to verify all dependencies are installed correctly.
Run this before starting the server.
"""

import sys

def test_imports():
    """Test all critical imports."""
    errors = []

    print("Testing imports...")
    print("-" * 50)

    # Core dependencies
    tests = [
        ("FastAPI", "fastapi"),
        ("Uvicorn", "uvicorn"),
        ("SQLAlchemy", "sqlalchemy"),
        ("Alembic", "alembic"),
        ("Pydantic", "pydantic"),
        ("Pydantic Settings", "pydantic_settings"),
        ("Email Validator", "email_validator"),
        ("Python Jose", "jose"),
        ("Passlib", "passlib"),
        ("Python Multipart", "multipart"),
        ("Aiosqlite", "aiosqlite"),
        ("Jinja2", "jinja2"),
        ("HTTPX", "httpx"),
        ("Pillow", "PIL"),
        ("Python Dotenv", "dotenv"),
        ("Aiofiles", "aiofiles"),
        ("Orjson", "orjson"),
    ]

    for name, module in tests:
        try:
            __import__(module)
            print(f"✓ {name:20} OK")
        except ImportError as e:
            print(f"✗ {name:20} MISSING")
            errors.append((name, module, str(e)))

    print("-" * 50)

    if errors:
        print(f"\n❌ {len(errors)} package(s) missing!\n")
        print("Install missing packages with:")
        print("  pip install -r requirements.txt\n")
        for name, module, error in errors:
            print(f"  pip install {module}")
        return False
    else:
        print("\n✅ All dependencies installed correctly!\n")
        return True


def test_app_imports():
    """Test application imports."""
    print("Testing application imports...")
    print("-" * 50)

    try:
        from app.core.config import settings
        print(f"✓ Config loaded (ENV: {settings.ENVIRONMENT})")
    except Exception as e:
        print(f"✗ Config failed: {e}")
        return False

    try:
        from app.db.base import Base
        print("✓ Database base imported")
    except Exception as e:
        print(f"✗ Database base failed: {e}")
        return False

    try:
        from app.db.models.collection import Collection
        from app.db.models.user import User, RefreshToken
        print("✓ Models imported")
    except Exception as e:
        print(f"✗ Models failed: {e}")
        return False

    try:
        from app.api.v1 import auth, collections
        print("✓ API routers imported")
    except Exception as e:
        print(f"✗ API routers failed: {e}")
        return False

    print("-" * 50)
    print("\n✅ Application imports successful!\n")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("FastCMS Dependency Check")
    print("=" * 50)
    print()

    # Test basic imports
    if not test_imports():
        sys.exit(1)

    # Test application imports
    if not test_app_imports():
        sys.exit(1)

    print("=" * 50)
    print("✅ Everything is ready!")
    print("=" * 50)
    print("\nYou can now run:")
    print("  python app/main.py")
    print("\nOr use the automated script:")
    print("  .\\fix_and_run.bat")
    print()
