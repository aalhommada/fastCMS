# FastCMS 🚀

**The AI-Native Backend-as-a-Service**

FastCMS is an open-source, self-hosted backend alternative to PocketBase, built with FastAPI and enhanced with AI superpowers. It combines the simplicity of traditional BaaS platforms with intelligent automation powered by LangChain and LangGraph.

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
- uv (recommended) or pip

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/fastCMS.git
cd fastCMS

# Install uv (if not already installed)
# On Windows:
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# On macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies with uv (fastest!)
uv pip install -e .

# Or with pip
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env and set your SECRET_KEY
# Generate with: openssl rand -hex 32

# Run database migrations
uv run alembic upgrade head

# Start the development server
uv run uvicorn app.main:app --reload

# Or run directly
python app/main.py
```

The API will be available at `http://localhost:8000`

- API Documentation: `http://localhost:8000/docs`
- Admin Dashboard: `http://localhost:8000/admin` (coming soon)

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

## 🎯 Roadmap

See [TODO.md](TODO.md) for the complete development roadmap.

### Current Status: Phase 1 - Foundation ✅

- [x] Project structure
- [x] Configuration system
- [x] Database setup (SQLAlchemy + Alembic)
- [x] Logging system
- [ ] Collections system (in progress)

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Inspired by [PocketBase](https://pocketbase.io/)
- Built with [FastAPI](https://fastapi.tiangolo.com/)
- AI powered by [LangChain](https://langchain.com/)

## 🌟 Star History

If you find FastCMS useful, please give it a star! ⭐

---

**Made with ❤️ by the FastCMS team**
