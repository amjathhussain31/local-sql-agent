# config.py
import os
from dotenv import load_dotenv
load_dotenv()

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

# DBHub
DBHUB_URL    = os.getenv("DBHUB_URL", "http://localhost:8080")

# Database
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL", "")

# Models

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GROQ_MODEL   = "openai/gpt-oss-120b"
USE_GROQ     = True    # set False to fall back to Gemini

# RAG
FAISS_INDEX_PATH = "data/faiss_index"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
TOP_K = 4

# Agent
MAX_RETRIES = 2
MAX_ITERATIONS = 6
MEMORY_WINDOW_K = 6