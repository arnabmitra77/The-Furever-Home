# Furever Home Chatbot API

AI-powered pet care chatbot using LangChain + LangGraph + ChromaDB.

## Architecture

```
Frontend (index.html) → POST /chat → FastAPI → LangGraph Agent
                                                    ├── ChromaDB (semantic search)
                                                    ├── Groq LLM (llama-3.1-8b)
                                                    └── Conversation memory
```

## Stack (100% Free)

| Component | Tool |
|-----------|------|
| LLM | Groq free tier (llama-3.1-8b-instant, 30 req/min) |
| Vector DB | ChromaDB (embedded, local) |
| Embeddings | HuggingFace all-MiniLM-L6-v2 (local) |
| Framework | LangChain + LangGraph |
| Server | FastAPI + Uvicorn |
| Hosting | Render.com free tier |

## Setup

### 1. Get a Groq API key (free)

1. Go to https://console.groq.com
2. Sign up and create an API key
3. Copy the key

### 2. Local development

```bash
cd chatbot-api
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# Build the vector store (first time)
python kb_loader.py

# Run the server
uvicorn main:app --reload --port 8000
```

### 3. Test it

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How often should I feed my puppy?"}'
```

### 4. Deploy to Render (free)

1. Push to GitHub
2. Go to https://render.com → New → Web Service
3. Connect your repo, select `chatbot-api/Dockerfile`
4. Add environment variable: `GROQ_API_KEY` = your key
5. Deploy!

Your API will be at: `https://furever-home-chatbot.onrender.com`

### 5. Update frontend

Change the chatbot widget in `index.html` to call your API:
```javascript
var CHATBOT_API_URL = 'https://furever-home-chatbot.onrender.com/chat';
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Send a message, get AI response |
| GET | `/health` | Health check |
| POST | `/refresh-kb` | Rebuild vector store from Google Sheets |

### POST /chat

**Request:**
```json
{
  "message": "How often should I feed my puppy?",
  "session_id": "optional-uuid-for-conversation-memory"
}
```

**Response:**
```json
{
  "answer": "Puppies should be fed 3-4 times a day until 6 months old, then transition to twice daily...",
  "session_id": "uuid",
  "sources": [{"url": "https://aspca.org/..."}]
}
```

## Adding Knowledge

### Option A: Google Sheets (current)
The KB sync cron job populates the `pet_care_kb` sheet. Run `/refresh-kb` to rebuild vectors.

### Option B: Local markdown files
Place `.md` files in `chatbot-api/knowledge_base/` — they'll be indexed automatically.

## Rate Limiting

- 20 requests per minute per IP (configurable via `MAX_REQUESTS_PER_MINUTE`)
- Returns HTTP 429 if exceeded
