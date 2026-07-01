"""
FastAPI server for The Furever Home chatbot.
Exposes a simple POST /chat endpoint that the frontend calls.
"""

import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage

from config import ALLOWED_ORIGINS, MAX_REQUESTS_PER_MINUTE
from agent import agent


# ── Rate Limiter ────────────────────────────────────────────────────────────

class RateLimiter:
    """Simple in-memory rate limiter by IP."""

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        # Clean old entries
        self.requests[key] = [
            t for t in self.requests[key] if now - t < self.window
        ]
        if len(self.requests[key]) >= self.max_requests:
            return False
        self.requests[key].append(now)
        return True


rate_limiter = RateLimiter(max_requests=MAX_REQUESTS_PER_MINUTE)

# ── Session Store (in-memory, for conversation history) ─────────────────────

sessions: dict[str, list] = {}
SESSION_MAX_MESSAGES = 20  # Keep last 20 messages per session


# ── App Setup ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load the vector store on startup."""
    from kb_loader import build_vector_store
    print("Loading knowledge base into vector store...")
    build_vector_store()
    print("Knowledge base ready!")
    yield


app = FastAPI(
    title="Furever Home Chatbot API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ── Request/Response Models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: list[dict] = []


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """Process a chat message and return AI response."""
    # Rate limit by IP
    client_ip = req.client.host if req.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment before trying again.",
        )

    # Get or create session history
    session_id = request.session_id
    if session_id not in sessions:
        sessions[session_id] = []

    # Build message history for the agent
    history = sessions[session_id]
    messages = history + [HumanMessage(content=request.message)]

    # Run the agent
    try:
        result = agent.invoke({"messages": messages, "context": "", "is_pet_care": True})
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail="I'm having trouble connecting right now. Please try again shortly.",
        )

    # Extract the assistant's response (last AI message)
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    if not ai_messages:
        raise HTTPException(status_code=500, detail="No response generated.")

    answer = ai_messages[-1].content

    # Extract sources from context if available
    sources = []
    context = result.get("context", "")
    if context and "URL:" in context:
        for line in context.split("\n"):
            if line.strip().startswith("URL:"):
                url = line.replace("URL:", "").strip()
                if url:
                    sources.append({"url": url})

    # Update session history (keep last N messages)
    sessions[session_id] = (
        history + [HumanMessage(content=request.message), AIMessage(content=answer)]
    )[-SESSION_MAX_MESSAGES:]

    return ChatResponse(
        answer=answer,
        session_id=session_id,
        sources=sources,
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "furever-home-chatbot"}


# ── RescueGroups API Proxy ──────────────────────────────────────────────────
# Proxies requests to RescueGroups.org API to avoid CORS restrictions

@app.post("/api/rescuegroups/{path:path}")
async def proxy_rescuegroups(path: str, request: Request):
    """Proxy POST requests to RescueGroups.org API (bypasses CORS)."""
    import httpx

    # Read the incoming request body and headers
    body = await request.body()
    target_url = f"https://api.rescuegroups.org/v5/public/{path}"

    # Forward query params
    query_string = str(request.url.query)
    if query_string:
        target_url += f"?{query_string}"

    # Get the Authorization header from the request
    auth_header = request.headers.get("Authorization", "")

    headers = {
        "Content-Type": "application/vnd.api+json",
        "Authorization": auth_header,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(target_url, content=body, headers=headers)
            return resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="RescueGroups API timeout")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Proxy error: {str(e)}")


@app.post("/refresh-kb")
async def refresh_kb():
    """Refresh the knowledge base (re-fetch from Google Sheets and rebuild vectors)."""
    try:
        from kb_loader import build_vector_store
        build_vector_store(force_rebuild=True)
        return {"status": "ok", "message": "Knowledge base refreshed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh KB: {str(e)}")
