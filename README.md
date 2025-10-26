# FastCMS 🚀

**The AI-Native Backend-as-a-Service**

FastCMS is an open-source, self-hosted backend, built with FastAPI and enhanced with AI superpowers. It combines the simplicity of traditional BaaS platforms with intelligent automation powered by LangChain and LangGraph.

## ✨ Features

- 🗄️ **Dynamic Collections** - Create database tables via API without writing SQL
- ⚡ **Auto-Generated REST API** - Instant CRUD endpoints for all collections
- 🔐 **Built-in Authentication** - Email/password + OAuth2 (Google, GitHub, etc.)
- 📁 **File Storage** - Local filesystem or S3-compatible storage with automatic thumbnails
- 🔄 **Real-time Updates** - Server-Sent Events (SSE) for live data synchronization
- 🎨 **Admin Dashboard** - Full-featured UI built with Jinja2 + Alpine.js
- 🔒 **Access Control Rules** - Fine-grained permissions with expression-based rules
- 🤖 **AI Agents** - Natural language queries, content moderation, semantic search, and more
- 🐍 **FastAPI** - Modern, async Python framework with automatic OpenAPI docs
- 📊 **SQLite** - Single-file database with optimizations (WAL mode, connection pooling)

## 🤖 AI-Powered Features (Unique!)

FastCMS is the **first FastAPI backend with native AI agents**:

- **Natural Language API Interface** - Talk to your API in plain English
- **Semantic Search** - Vector-based search with embeddings
- **Content Moderation** - Automatic spam/hate speech detection
- **Data Quality Monitoring** - AI suggests validation rules and detects anomalies
- **Auto-Documentation** - Generate API docs from your schema
- **Smart Test Data** - Generate realistic fake data that understands relationships
- **Local LLM Support** - Privacy-first with Ollama (zero cost, zero data leaks)

## 🚀 Quick Start

### Prerequisites

- Python 3.11+

### Installation

#### Windows (Easiest Method)

```powershell
# 1. Clone the repository
git clone https://github.com/yourusername/fastCMS.git
cd fastCMS

# 2. Run the automated setup and start script
.\fix_and_run.bat
```

That's it! The script will:

- Create a virtual environment
- Install all dependencies
- Run database migrations
- Start the server

#### Manual Setup (All Platforms)

```bash
# 1. Clone the repository
git clone https://github.com/aalhommada/fastCMS.git
cd fastCMS

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.venv\Scripts\activate.bat
# macOS/Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Copy environment file
cp .env.example .env
# Edit .env and set your SECRET_KEY (generate with: openssl rand -hex 32)

# 6. Run database migrations
alembic upgrade head

# 7. Start the development server
python app/main.py
# Or with auto-reload:
uvicorn app.main:app --reload
```

### Access Points

Once the server is running:

- **API Documentation (Swagger):** http://localhost:8000/docs
- **Alternative Docs (ReDoc):** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health
- **Admin Dashboard:** http://localhost:8000/admin (coming in Phase 7)

## 📦 Tech Stack

- **FastAPI** - High-performance async web framework
- **SQLAlchemy 2.0** - Modern async ORM
- **SQLite** - Single-file database with optimizations
- **Pydantic v2** - Data validation with excellent performance
- **Alembic** - Database migrations with auto-generation
- **JWT** - Secure token-based authentication
- **Bcrypt** - Password hashing (cost factor 12)
- **LangChain** - AI agent framework
- **LangGraph** - Multi-agent workflow orchestration
- **FAISS/Qdrant** - Vector database for semantic search

## 🏗️ Project Structure

```
fastCMS/
├── app/
│   ├── api/v1/          # API endpoints
│   ├── core/            # Configuration, security, logging
│   ├── db/              # Database models & session
│   ├── schemas/         # Pydantic models
│   ├── services/        # Business logic
│   ├── ai/              # AI agents & workflows
│   └── main.py          # FastAPI app entry
├── migrations/          # Alembic migrations
├── tests/               # Test suite
├── data/                # SQLite database & files
└── pyproject.toml       # Dependencies
```

## 📖 Documentation

- [Installation Guide](docs/installation.md) (coming soon)
- [API Reference](docs/api.md) (coming soon)
- [AI Features Guide](docs/ai-features.md) (coming soon)
- [Deployment Guide](docs/deployment.md) (coming soon)

## 📚 API Examples

### Register a User

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!",
    "name": "John Doe"
  }'
```

### Login

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

### Create a Collection

```bash
curl -X POST "http://localhost:8000/api/v1/collections" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "posts",
    "type": "base",
    "schema": [
      {
        "name": "title",
        "type": "text",
        "validation": {"required": true, "min": 3, "max": 200}
      },
      {
        "name": "content",
        "type": "editor"
      },
      {
        "name": "published",
        "type": "bool"
      }
    ]
  }'
```

See [test_auth.md](test_auth.md) for more detailed API examples.

## 🎯 Roadmap

See [TODO.md](TODO.md) for the complete development roadmap.

### Current Status: Phase 3 - Authentication ✅

- [x] Phase 1: Project foundation
- [x] Phase 2: Collections system (dynamic tables)
- [x] Phase 3: Authentication (JWT, register, login, refresh tokens)
- [ ] Phase 4: Records CRUD API (in progress)
- [ ] Phase 5: File uploads & storage
- [ ] Phase 6: Real-time features (SSE/WebSocket)
- [ ] Phase 7: Admin dashboard UI
- [ ] Phase 8: AI agents integration

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- AI powered by [LangChain](https://langchain.com/)

## 🌟 Star History

If you find FastCMS useful, please give it a star! ⭐

---

**Made with ❤️ by the FastCMS team**
