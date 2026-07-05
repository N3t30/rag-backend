from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Tuple
from uuid import uuid4

import requests
from langchain.storage import LocalFileStore
from langchain_core.documents import Document
from langchain_ollama import ChatOllama, OllamaEmbeddings

try:
    from langchain_chroma import Chroma
except ImportError:  # pragma: no cover - fallback for environments
    # without chromadb native bindings
    Chroma = None

try:
    from unstructured.partition.pdf import partition_pdf
except ImportError:  # pragma: no cover - fallback for lean environments
    partition_pdf = None

try:
    from .config import (
        CHAT_MODEL,
        CHROMA_PATH,
        DOCSTORE_PATH,
        EMBEDDING_MODEL,
        OLLAMA_HOST,
        REQUEST_TIMEOUT_SECONDS,
        ensure_storage_dirs,
    )
except ImportError:  # pragma: no cover - fallback for direct script execution
    from config import (
        CHAT_MODEL,
        CHROMA_PATH,
        DOCSTORE_PATH,
        EMBEDDING_MODEL,
        OLLAMA_HOST,
        REQUEST_TIMEOUT_SECONDS,
        ensure_storage_dirs,
    )


def _check_ollama_models() -> List[str]:
    """Verifica se o Ollama está acessível e retorna os modelos."""
    try:
        response = requests.get(
            f"{OLLAMA_HOST}/api/tags",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            model.get("name", "")
            for model in payload.get("models", [])
            if model.get("name")
        ]
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Ollama não está acessível. Inicie o serviço com 'ollama serve'."
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            "Ollama demorou demais para responder. "
            "Verifique se o serviço está carregando o modelo."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Falha ao consultar o Ollama: {exc}") from exc


def _normalize_model_name(model_name: str) -> str:
    """Normaliza nomes de modelos do Ollama removendo o sufixo :latest."""
    if not model_name:
        return model_name
    return model_name.removesuffix(":latest")


def _ensure_required_models() -> None:
    """Garante que os modelos usados pela aplicação estejam instalados."""
    available_models = _check_ollama_models()
    normalized_available = {
        _normalize_model_name(model_name)
        for model_name in available_models
    }

    missing_models = [
        model_name
        for model_name in (CHAT_MODEL, EMBEDDING_MODEL)
        if _normalize_model_name(model_name) not in normalized_available
    ]
    if missing_models:
        missing_list = ", ".join(missing_models)
        raise RuntimeError(
            "Modelos ausentes no Ollama: "
            f"{missing_list}. Execute 'ollama pull <nome>' para baixá-los."
        )


def _build_chat_model() -> ChatOllama:
    return ChatOllama(
        model=CHAT_MODEL,
        base_url=OLLAMA_HOST,
        temperature=0,
    )


def _build_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_HOST,
    )


def _extract_pdf_elements(pdf_path: Path) -> List[Tuple[str, str]]:
    """Extrai textos e tabelas do PDF, preferindo o unstructured."""
    if partition_pdf is not None:
        try:
            elements = partition_pdf(
                filename=str(pdf_path),
                strategy="fast",
                infer_table_structure=True,
                chunking_strategy="by_title",
            )
        except Exception as exc:
            raise RuntimeError(
                f"Não foi possível ler o PDF '{pdf_path.name}' "
                f"com o unstructured: {exc}"
            ) from exc

        extracted_items: List[Tuple[str, str]] = []
        for element in elements:
            text = getattr(element, "text", None) or str(element)
            if not text or not text.strip():
                continue

            category = str(getattr(element, "category", "")).lower()
            kind = "table" if "table" in category else "text"
            extracted_items.append((kind, text.strip()))

        if extracted_items:
            return extracted_items

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "Nenhuma biblioteca de leitura de PDF ficou disponível. "
            "Instale 'pypdf' ou 'unstructured[pdf]'."
        ) from exc

    try:
        reader = PdfReader(str(pdf_path))
        extracted_items = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                extracted_items.append(("text", text.strip()))
    except Exception:
        extracted_items = []

    if not extracted_items:
        return [("text", f"Arquivo PDF sem texto extraível: {pdf_path.name}")]

    return extracted_items


def _summarize_content(chat_model: ChatOllama, content: str) -> str:
    """Gera um resumo curto em português para indexação."""
    prompt = (
        "Resuma o conteúdo abaixo em português, de forma objetiva e curta, "
        "para fins de indexação e busca:\n\n"
        f"{content}"
    )

    try:
        response = chat_model.invoke(prompt)
        summary = (
            response.content.strip()
            if hasattr(response, "content")
            else str(response).strip()
        )
        return summary or "Resumo indisponível"
    except Exception as exc:
        message = str(exc).lower()
        if "connection refused" in message or "connection error" in message:
            raise RuntimeError(
                "Ollama não está rodando. Inicie o serviço com 'ollama serve'."
            ) from exc
        if "model" in message and (
            "not found" in message or "does not exist" in message
        ):
            raise RuntimeError(
                f"Modelo '{CHAT_MODEL}' não encontrado. "
                f"Execute 'ollama pull {CHAT_MODEL}'."
            ) from exc
        msg = f"Erro ao resumir conteúdo com o Ollama: {exc}"
        raise RuntimeError(msg) from exc


def _normalize_upload_content(content: object) -> bytes:
    """Converte o conteúdo recebido no upload para bytes."""
    if isinstance(content, (bytes, bytearray, memoryview)):
        return bytes(content)
    if isinstance(content, str):
        return content.encode("utf-8")
    return str(content).encode("utf-8")


def ingest_pdf(pdf_path: str | Path) -> dict:
    """Processa um PDF e armazena resumos no Chroma e conteúdos originais."""
    ensure_storage_dirs()
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("Apenas arquivos PDF são aceitos.")

    _ensure_required_models()

    chat_model = _build_chat_model()
    embeddings = _build_embeddings()
    docstore = LocalFileStore(str(DOCSTORE_PATH))
    if Chroma is None:
        vectorstore = None
    else:
        vectorstore = Chroma(
            collection_name="rag_documents",
            embedding_function=embeddings,
            persist_directory=str(CHROMA_PATH),
        )

    elements = _extract_pdf_elements(path)
    indexed_texts = 0
    indexed_tables = 0

    for kind, content in elements:
        doc_id = str(uuid4())
        summary = _summarize_content(chat_model, content)
        docstore.mset([(doc_id, content.encode("utf-8"))])
        if vectorstore is not None:
            vectorstore.add_documents(
                [Document(page_content=summary, metadata={"doc_id": doc_id})]
            )
        if kind == "table":
            indexed_tables += 1
        else:
            indexed_texts += 1

    if vectorstore is not None:
        vectorstore.persist()

    return {
        "file": path.name,
        "texts_indexed": indexed_texts,
        "tables_indexed": indexed_tables,
        "total_indexed": indexed_texts + indexed_tables,
    }


async def ingest_uploaded_pdf(uploaded_file) -> dict:
    """Salva um arquivo carregado em um arquivo temporário e
    realiza a ingestão.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        content = await uploaded_file.read()
        content_bytes = _normalize_upload_content(content)
        if not content_bytes:
            raise ValueError("O arquivo PDF está vazio.")
        temp_file.write(content_bytes)
        temp_path = Path(temp_file.name)

    try:
        return ingest_pdf(temp_path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
