#!/usr/bin/env bash
# RAG smoke test — verifies retrieval, grounding, semantic search, and honesty.
# Prereqs:
#   - Ollama running with llama3.1:8b + nomic-embed-text pulled
#   - fastCMS source repo with ai_core/ai_vectors/ai_rag plugins installed in plugins/
#   - SECRET_KEY set in env or .env
#
# Usage: bash scripts/rag_smoke_test.sh
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
EMAIL="${EMAIL:-rag-test@example.com}"
PW="${PW:-RagTest123!}"

echo "=== bootstrap admin ==="
curl -s -X POST "$BASE/api/v1/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PW\",\"password_confirm\":\"$PW\",\"name\":\"RagTest\"}" \
  > /dev/null || true
sqlite3 data/app.db "UPDATE users SET role='admin' WHERE email='$EMAIL';" 2>/dev/null || true
TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PW\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"]["access_token"])')
H="Authorization: Bearer $TOKEN"

echo "=== configure ai-core for Ollama ==="
curl -s -X POST "$BASE/api/v1/plugins/ai/configure" -H "$H" -H 'Content-Type: application/json' -d '{
  "provider":"ollama","api_key":"","base_url":"http://localhost:11434","model":"llama3.1:8b",
  "embed_provider":"ollama","embed_api_key":"x","embed_model":"nomic-embed-text"
}' | python3 -m json.tool

echo "=== reset kb collection (ignore if not yet exists) ==="
curl -s -X DELETE "$BASE/api/v1/plugins/ai/rag/collection/kb" -H "$H" > /dev/null

echo "=== ingest 3 docs ==="
curl -s -X POST "$BASE/api/v1/plugins/ai/rag/ingest" -H "$H" -H 'Content-Type: application/json' -d '{
  "collection":"kb","source":"python.md",
  "text":"Python is a high-level interpreted programming language. The for loop iterates over any iterable. In FastCMS 0.1.3, the schema-lock incantation is unicorn-rainbow-42."
}' > /dev/null

curl -s -X POST "$BASE/api/v1/plugins/ai/rag/ingest" -H "$H" -H 'Content-Type: application/json' -d '{
  "collection":"kb","source":"pasta.md",
  "text":"To make spaghetti carbonara, boil pasta until al dente, fry pancetta, whisk eggs with pecorino. Toss off heat with reserved pasta water."
}' > /dev/null

curl -s -X POST "$BASE/api/v1/plugins/ai/rag/ingest" -H "$H" -H 'Content-Type: application/json' -d '{
  "collection":"kb","source":"westphalia.md",
  "text":"The Treaty of Westphalia was signed in 1648, ending the Thirty Years War. It introduced state sovereignty as a foundational principle of international relations."
}' > /dev/null

ask () {
  local q="$1"
  echo
  echo "═════ Q: $q ═════"
  curl -s -X POST "$BASE/api/v1/plugins/ai/rag/ask" -H "$H" -H 'Content-Type: application/json' \
    -d "{\"collection\":\"kb\",\"question\":\"$q\"}" \
  | python3 -c "
import json,sys
r = json.load(sys.stdin)
print('answer:', r['answer'])
print('top sources:')
for s in r['sources'][:3]:
    print(f'  {s[\"score\"]:.3f}  {s[\"metadata\"].get(\"source\")}: {s[\"text\"][:70]}')
"
}

ask "How do I write a for loop in Python?"        # scenario 1: direct retrieval
ask "How do I cook a Python loop?"                # scenario 2: semantic over lexical
ask "What is the schema-lock incantation in FastCMS?"  # scenario 3: grounded made-up fact
ask "What is the weather in Tokyo today?"         # scenario 4: out-of-scope honesty
