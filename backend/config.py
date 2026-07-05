from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CHROMA_PATH = BASE_DIR / "chroma_db"
DOCSTORE_PATH = BASE_DIR / "docstore"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:3b")
EMBEDDING_MODEL = os.getenv(
    "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
)
REQUEST_TIMEOUT_SECONDS = int(
    os.getenv("OLLAMA_TIMEOUT_SECONDS", "120")
)
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "4"))


def ensure_storage_dirs() -> None:
    """Cria os diretórios locais usados pelo Chroma e pelo DocStore."""
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    DOCSTORE_PATH.mkdir(parents=True, exist_ok=True)
