# FastCMS Quick Start Guide

## Step 1: Install Dependencies

### Option A: Using pip (Recommended for quick start)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Option B: Using Poetry (Recommended for development)

```bash
# Install Poetry first (if not installed)
# https://python-poetry.org/docs/#installation

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

## Step 2: Configure Environment

```bash
# .env file is already created with development defaults
# You can modify it if needed, especially:
# - SECRET_KEY (generate with: openssl rand -hex 32)
# - DATABASE_URL
# - Admin credentials
```

## Step 3: Create Database and Run Migrations

```bash
# Generate initial migration
alembic revision --autogenerate -m "initial collections table"

# Apply migrations
alembic upgrade head
```

## Step 4: Start the Server

```bash
# Using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python
python app/main.py
```

## Step 5: Test the API

Visit: http://localhost:8000

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Collections API**: http://localhost:8000/api/v1/collections

## Quick Test with curl

```bash
# Create a collection
curl -X POST "http://localhost:8000/api/v1/collections" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "posts",
    "type": "base",
    "schema": [
      {
        "name": "title",
        "type": "text",
        "validation": {
          "required": true,
          "max_length": 200
        }
      },
      {
        "name": "content",
        "type": "editor",
        "validation": {
          "required": true
        }
      },
      {
        "name": "published",
        "type": "bool",
        "validation": {
          "required": false
        }
      }
    ]
  }'

# List all collections
curl "http://localhost:8000/api/v1/collections"
```

## Common Issues

### Import Error for Alembic

If you get "No module named alembic", ensure you're in the virtual environment:
```bash
# Check if venv is activated (should see (venv) in prompt)
which python  # Should point to venv/bin/python
```

### Database Locked

If SQLite shows "database is locked", restart the server.

### ModuleNotFoundError

Make sure all dependencies are installed:
```bash
pip install -r requirements.txt
```

## Next Steps

1. **Add Authentication** - Implement user registration and login
2. **Build Records API** - CRUD operations for dynamic collections
3. **Add File Upload** - Support file fields with storage
4. **Enable AI Features** - Integrate LangChain agents

Check `TODO.md` for the complete roadmap!
