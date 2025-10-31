# FastCMS

Self-hosted Backend-as-a-Service built with FastAPI. Create dynamic collections, REST APIs, and authentication without writing SQL.

## Features Status

### Core Features
- [x] Dynamic Collections - Create database tables via API
- [x] Authentication - JWT-based auth with register/login
- [x] CRUD API - Create, read, update, delete records
- [ ] File Storage - Upload and serve files
- [ ] Real-time Updates - Server-Sent Events
- [ ] Admin Dashboard - Web UI for management
- [ ] Access Control - Permission rules per collection

### AI Features (Planned)
- [ ] Natural Language API Interface
- [ ] Semantic Search - Vector-based search
- [ ] Content Moderation
- [ ] Data Quality Monitoring
- [ ] Auto-Documentation
- [ ] Smart Test Data Generation

## Installation

### Windows
```bash
git clone https://github.com/aalhommada/fastCMS.git
cd fastCMS
.\fix_and_run.bat
```

### Manual Setup
```bash
git clone https://github.com/aalhommada/fastCMS.git
cd fastCMS
python -m venv .venv

# Activate virtual environment
# Windows: .venv\Scripts\activate.bat
# Linux/Mac: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env and set SECRET_KEY

alembic upgrade head
python app/main.py
```

### Access
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Tech Stack

- FastAPI - Async web framework
- SQLAlchemy 2.0 - Async ORM
- SQLite - Database with WAL mode
- Pydantic v2 - Data validation
- Alembic - Database migrations
- JWT - Token-based authentication
- LangChain/LangGraph - AI framework (planned)

## Project Structure

```
fastCMS/
├── app/
│   ├── api/v1/          # API endpoints
│   ├── core/            # Configuration, security
│   ├── db/              # Database models
│   ├── schemas/         # Pydantic models
│   ├── services/        # Business logic
│   └── main.py          # App entry
├── migrations/          # Alembic migrations
├── tests/               # Tests
└── data/                # Database & files
```

## API Examples

### Register
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!", "password_confirm": "SecurePass123!", "name": "John Doe"}'
```

### Login
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}'
```

### Create Collection
```bash
curl -X POST "http://localhost:8000/api/v1/collections" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "posts",
    "type": "base",
    "schema": [
      {"name": "title", "type": "text", "validation": {"required": true}},
      {"name": "content", "type": "editor"},
      {"name": "published", "type": "bool"}
    ]
  }'
```

## License

MIT License
