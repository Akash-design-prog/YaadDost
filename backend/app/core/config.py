"""Settings, read from environment variables once at import time."""
import os

# Where your Gemma server lives: local Ollama, or the Colab tunnel URL (see colab/).
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
MODEL = os.environ.get("GEMMA_MODEL", "gemma4:e4b")
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "120"))

MAX_NOTES = 8000
