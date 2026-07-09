from __future__ import annotations

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from .config import OLLAMA_HOST
    from .ingest import ingest_uploaded_pdf
    from .retriever import query as run_query
except ImportError:  # pragma: no cover - fallback for direct script execution
    from config import OLLAMA_HOST
    from ingest import ingest_uploaded_pdf
    from retriever import query as run_query


class QueryRequest(BaseModel):
    pergunta: str


app = FastAPI(title="RAG Backend Local", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict:
    """Verifica a disponibilidade do Ollama e os modelos instalados."""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=20)
        response.raise_for_status()
        payload = response.json()
        available_models = [
            model.get("name", "")
            for model in payload.get("models", [])
            if model.get("name")
        ]
        return {
            "status": "ok",
            "ollama_available": True,
            "models": available_models,
        }
    except requests.exceptions.ConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail="Ollama não está acessível. Inicie com 'ollama serve'.",
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise HTTPException(
            status_code=504,
            detail="Ollama demorou demais para responder.",
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao consultar o Ollama: {exc}",
        ) from exc


@app.post("/ingest")
async def ingest_pdf(file: UploadFile = File(...)) -> dict:
    """Recebe um PDF e executa o pipeline de ingestão."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Apenas arquivos PDF são aceitos.",
        )

    try:
        result = await ingest_uploaded_pdf(file)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erro inesperado durante a ingestão: {exc}",
        ) from exc


@app.post("/query")
def query(payload: QueryRequest) -> dict:
    """Recebe uma pergunta e retorna uma resposta com as fontes usadas."""
    try:
        return run_query(payload.pergunta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erro inesperado durante a busca: {exc}",
        ) from exc
