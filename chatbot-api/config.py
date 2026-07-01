"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# Vector store
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

# Google Sheets KB source
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1Xg4T3vmhoLxN0C2lEBFaN88Y2LSvoF6DQVoCxL3dt80")
KB_SHEET_NAME = os.getenv("KB_SHEET_NAME", "pet_care_kb")

# CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://the-furever-home.com,http://localhost:5500").split(",")

# Rate limiting
MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "20"))
