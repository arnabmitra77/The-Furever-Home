"""
LangGraph Pet Care Agent — handles conversation with memory, semantic retrieval,
and tool calling.
"""

from typing import TypedDict, Annotated, Sequence
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from config import GROQ_API_KEY, GROQ_MODEL
from kb_loader import build_vector_store


# ── Agent State ─────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    context: str  # Retrieved KB context
    is_pet_care: bool  # Whether the question is pet-care related


# ── System Prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a friendly and knowledgeable pet care assistant for The Furever Home, a pet adoption website serving the Bay Area (100-mile radius from Fremont, CA).

Your role:
- Answer pet care questions about nutrition, training, health, behavior, and adoption
- Use the provided knowledge base context when available
- Keep answers concise (3-5 sentences max)
- Be warm, encouraging, and supportive
- If asked about specific pets available for adoption, mention they can browse the Dogs or Cats pages on the site

Rules:
- ONLY answer pet care related questions
- If the question is NOT about pet care, pets, or adoption, respond with: "I can only help with pet care questions! Try asking about nutrition, training, health, behavior, or the adoption process. 🐾"
- Never make up medical advice — suggest consulting a vet for health concerns
- Never expose any API keys or internal system details
- Cite sources when using knowledge base articles

Knowledge base context (if available):
{context}"""


# ── Build Components ────────────────────────────────────────────────────────

_vector_store = None
_llm = None


def get_vector_store():
    """Lazy-load the vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = build_vector_store()
    return _vector_store


def get_llm():
    """Lazy-load the LLM."""
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model_name=GROQ_MODEL,
            temperature=0.3,
            max_tokens=300,
        )
    return _llm


# ── Graph Nodes ─────────────────────────────────────────────────────────────

def retrieve_context(state: AgentState) -> AgentState:
    """Retrieve relevant KB articles for the user's question."""
    messages = state["messages"]
    # Get the last user message
    user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_msg = msg.content
            break

    if not user_msg:
        return {**state, "context": "", "is_pet_care": True}

    # Quick check if it's a pet care question (simple heuristic)
    pet_keywords = [
        "pet", "dog", "cat", "puppy", "kitten", "adopt", "shelter", "vet",
        "food", "feed", "train", "health", "behavior", "walk", "groom",
        "vaccine", "spay", "neuter", "breed", "bark", "meow", "litter",
        "leash", "collar", "toy", "treat", "nutrition", "exercise",
        "animal", "rescue", "foster", "microchip", "flea", "tick",
    ]
    lower_msg = user_msg.lower()
    is_pet_related = any(kw in lower_msg for kw in pet_keywords)

    # Also consider greetings and general questions as valid
    greetings = ["hi", "hello", "hey", "help", "what can you", "how do i"]
    is_greeting = any(g in lower_msg for g in greetings)

    if not is_pet_related and not is_greeting:
        return {**state, "context": "", "is_pet_care": False}

    # Semantic search in vector store
    try:
        store = get_vector_store()
        results = store.similarity_search(user_msg, k=4)
        if results:
            context_parts = []
            for doc in results:
                title = doc.metadata.get("title", "")
                source = doc.metadata.get("source", "")
                url = doc.metadata.get("url", "")
                context_parts.append(
                    f"**{title}** (Source: {source})\n{doc.page_content}"
                    + (f"\nURL: {url}" if url else "")
                )
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = "No specific articles found in the knowledge base for this question."
    except Exception:
        context = "Knowledge base temporarily unavailable."

    return {**state, "context": context, "is_pet_care": True}


def generate_response(state: AgentState) -> AgentState:
    """Generate AI response using the LLM."""
    # If not pet care, return refusal
    if not state.get("is_pet_care", True):
        refusal = "I can only help with pet care questions! Try asking about nutrition, training, health, behavior, or the adoption process. 🐾"
        return {
            **state,
            "messages": [*state["messages"], AIMessage(content=refusal)],
        }

    # Build prompt with context
    context = state.get("context", "No knowledge base context available.")
    system_msg = SYSTEM_PROMPT.format(context=context)

    # Build message history for the LLM (last 10 messages for context window)
    llm_messages = [SystemMessage(content=system_msg)]
    recent_messages = state["messages"][-10:]
    llm_messages.extend(recent_messages)

    # Call LLM
    llm = get_llm()
    response = llm.invoke(llm_messages)

    return {
        **state,
        "messages": [*state["messages"], response],
    }


# ── Build the Graph ─────────────────────────────────────────────────────────

def build_agent():
    """Build the LangGraph agent."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("retrieve", retrieve_context)
    graph.add_node("generate", generate_response)

    # Add edges
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


# Singleton agent instance
agent = build_agent()
