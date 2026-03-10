# FastCMS

A modern Backend-as-a-Service that lets you create databases, APIs, and manage content without writing code. Think of it as your own personal backend that handles everything from user authentication to file uploads.

## What Does It Do?

FastCMS is like having a ready-made backend for your app. Instead of spending weeks building user login systems, databases, and APIs, you can:

- **Create databases instantly** - Just describe what you need (like "users" or "blog posts") and get a working database
- **Auth Collections** 🔐 - Create multiple user authentication systems (customers, vendors, admins) with auto-hashed passwords and JWT tokens
- **View Collections** 📊 **NEW!** - Create virtual collections that compute data in real-time (statistics, reports, analytics) with JOINs and aggregations
- **Manage users** - Built-in login, registration, password reset, and social login (Google, GitHub, Microsoft)
- **Store files** - Upload and serve images, PDFs, and other files with **automatic thumbnail generation**
- **Search and filter** - Find exactly what you need with simple queries
- **Control access** - Decide who can see, create, or edit each piece of content
- **Get notified** - Set up webhooks to know when things change
- **Admin panel** - Manage everything through a clean web interface
- **Backup & Restore** - One-click database backups with full restore capability
- **Import/Export** - Move collections between environments easily

### AI Features (via Plugins)

FastCMS supports AI capabilities through its plugin system. Install only what you need:

- **Vector Search** - Semantic search on your collections
- **RAG** - Upload documents, ask questions in natural language
- **AI Agents** - Autonomous agents that work with your data
- **Content Generation** - Auto-generate content with any LLM provider

See the [AI Plugins documentation](https://fastcms.dev/docs/plugins) for setup instructions.

## How to Run It

### 1. Get the Code

```bash
git clone https://github.com/aalhommada/fastCMS.git
cd fastCMS
```

### 2. Set Up Python Environment

```bash
# Create a virtual environment
python -m venv .venv

# Activate it
# On Mac/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Settings

```bash
# Copy the example environment file
cp .env.example .env

# Generate a secret key
openssl rand -hex 32

# Open .env and paste your secret key into SECRET_KEY=
```

### 5. Start the Server

```bash
# Option 1: Run as a module (recommended)
python -m app.main

# Option 2: Use uvicorn directly (best for development)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Option 3: If you get "ModuleNotFoundError: No module named 'app'"
export PYTHONPATH=$PWD:$PYTHONPATH
python app/main.py
```

### 6. Database Migrations

When you change the database models, you need to create and apply migrations:

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head
```

That's it! Your backend is running.

## Where to Go

Once running, open your browser:

- **API Docs** - http://localhost:8000/docs (interactive API playground)
- **Admin Panel** - http://localhost:8000/admin (requires admin account)
- **Health Check** - http://localhost:8000/health (verify it's running)

## First Steps

### Create Your First User

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "password": "YourPassword123!",
    "password_confirm": "YourPassword123!",
    "name": "Your Name"
  }'
```

### Create a Database Collection

Collections are like tables in a database. Here's how to create one for blog posts:

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

### Add Some Data

```bash
curl -X POST "http://localhost:8000/api/v1/collections/posts/records" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Post",
    "content": "Hello, World!",
    "published": true
  }'
```

### Search Your Data

```bash
# Find published posts
curl "http://localhost:8000/api/v1/collections/posts/records?filter=published=true"

# Text search
curl "http://localhost:8000/api/v1/collections/posts/records?filter=title~Hello"

# Sort by newest first
curl "http://localhost:8000/api/v1/collections/posts/records?sort=-created"
```

## Optional Features

### Social Login

Add these to your `.env` file to let users log in with Google, GitHub, or Microsoft:

```bash
GOOGLE_CLIENT_ID=your_id_here
GOOGLE_CLIENT_SECRET=your_secret_here
```

Then users can visit: http://localhost:8000/api/v1/oauth/login/google

## Common Questions

**Where is my data stored?**
In a SQLite database file at `data/app.db`

**How do I make an admin user?**
After creating a user, run:
```bash
sqlite3 data/app.db "UPDATE users SET role = 'admin' WHERE email = 'your@email.com';"
```

**Can I use this in production?**
Yes! Just make sure to:
- Change `DEBUG=false` in `.env`
- Use a strong `SECRET_KEY`
- Set up proper CORS origins
- Use PostgreSQL instead of SQLite for better performance

**Do I need AI features?**
No! The AI features are completely optional. The core backend works great without them.

## Built With

- **FastAPI** - Fast, modern Python web framework
- **SQLAlchemy** - Database toolkit
- **SQLite** - Database (can use PostgreSQL too)
- **JWT** - Secure authentication tokens
- **Plugin System** - Extensible with AI and other plugins

## Project Structure

```
fastCMS/
├── app/
│   ├── api/v1/        # All API endpoints
│   ├── admin/         # Admin web interface
│   ├── core/          # Settings & security
│   ├── db/            # Database models
│   └── main.py        # Start here
├── data/              # Your database & files
└── .env               # Your settings
```

## New Features

FastCMS includes:

### Core Improvements
- **Automatic Image Thumbnails** - 3 sizes (100px, 300px, 500px) generated on upload
- **Database Backup API** - Create, list, download, and restore backups via API
- **Collection Import/Export** - Export/import schemas and data as JSON
- **Advanced Admin UI** - Complete CRUD interface for all operations

### AI Features (via Plugins)
- **Semantic Search** - Find content by meaning, not just keywords
- **RAG** - Upload documents and ask questions in natural language
- **AI Agents** - Autonomous agents that interact with your data
- **Multi-Provider** - OpenAI, Anthropic, Ollama (local) — your choice

### Developer Experience
- **Python Ecosystem** - Use any Python library
- **Type Safety** - Full type hints throughout
- **OpenAPI Docs** - Interactive API documentation at /docs
- **Async First** - Built on modern async Python

## API Quick Reference

### Backups (Admin Only)
```bash
# Create backup
curl -X POST http://localhost:8000/api/v1/backups \
  -H "Authorization: Bearer YOUR_TOKEN"

# List backups
curl http://localhost:8000/api/v1/backups \
  -H "Authorization: Bearer YOUR_TOKEN"

# Download backup
curl http://localhost:8000/api/v1/backups/backup_20250116.zip/download \
  -H "Authorization: Bearer YOUR_TOKEN" -O

# Restore backup (⚠️ overwrites current data!)
curl -X POST http://localhost:8000/api/v1/backups/backup_20250116.zip/restore \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Collection Import/Export (Admin Only)
```bash
# Export collection with data
curl http://localhost:8000/api/v1/collections/{id}/export?include_data=true \
  -H "Authorization: Bearer YOUR_TOKEN" > collection.json

# Import collection
curl -X POST http://localhost:8000/api/v1/collections/import \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d @collection.json
```

## Need Help?

- Check http://localhost:8000/docs for full API documentation
- Look at the example curl commands above
- Browse the code - it's well documented!

## License

MIT License - Free to use for anything!
