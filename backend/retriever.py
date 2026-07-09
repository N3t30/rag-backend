from __future__ import annotations

from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain.storage import LocalFileStore 
from langchain_ollama import ChatOllama, OllamaEmbeddings

try:
    from langchain_chroma import Chroma
except ImportError:  # pragma: no cover - fallback for environments
    # without chromadb native bindings
    Chroma = None

try:
    from .config import (
        CHAT_MODEL,
        CHROMA_PATH,
        DOCSTORE_PATH,
        DEFAULT_TOP_K,
        EMBEDDING_MODEL,
        OLLAMA_HOST,
    )
except ImportError:  # pragma: no cover - fallback for direct script execution
    from config import (
        CHAT_MODEL,
        CHROMA_PATH,
        DOCSTORE_PATH,
        DEFAULT_TOP_K,
        EMBEDDING_MODEL,
        OLLAMA_HOST,
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


def build_retriever(k: int = DEFAULT_TOP_K) -> MultiVectorRetriever:
    """Cria o retriever multi-vector usando Chroma e LocalFileStore."""
    embeddings = _build_embeddings()
    docstore = LocalFileStore(str(DOCSTORE_PATH))
    if Chroma is None:
        return None

    vectorstore = Chroma(
        collection_name="rag_documents",
        embedding_function=embeddings,
        persist_directory=str(CHROMA_PATH),
    )
    return MultiVectorRetriever(
        vectorstore=vectorstore,
        docstore=docstore,
        id_key="doc_id",
        search_kwargs={"k": k},
    )


def query(question: str, k: int = DEFAULT_TOP_K) -> dict:
    """Busca documentos relevantes, monta um contexto e gera uma resposta."""
    if not question or not question.strip():
        raise ValueError("A pergunta não pode ficar vazia.")

    retriever = build_retriever(k=k)
    if retriever is None:
        return {
            "resposta": (
                "O backend não pode executar buscas vetoriais neste "
                "ambiente porque o ChromaDB não está disponível."
            ),
            "fontes": [],
        }

    summary_docs = retriever.vectorstore.similarity_search(question, k=k)

    if not summary_docs:
        return {
            "resposta": (
                "Não encontrei conteúdo relevante para "
                "responder à pergunta."
            ),
            "fontes": [],
        }

    doc_ids = [
        doc.metadata.get("doc_id")
        for doc in summary_docs
        if doc.metadata.get("doc_id")
    ]
    original_docs = []
    if doc_ids:
        original_docs = [
            doc for doc in retriever.docstore.mget(doc_ids) if doc is not None
        ]

    context_parts = []
    for doc in original_docs:
        if isinstance(doc, bytes):
            context_parts.append(doc.decode("utf-8", errors="replace"))
        elif isinstance(doc, memoryview):
            context_parts.append(bytes(doc).decode("utf-8", errors="replace"))
        elif isinstance(doc, str):
            context_parts.append(doc)
        else:
            context_parts.append(str(doc))

    if not context_parts:
        return {
            "resposta": (
                "Não foi possível recuperar o conteúdo original associado "
                "aos trechos encontrados."
            ),
            "fontes": doc_ids,
        }

    context_text = "\n\n".join(context_parts)
    prompt = (
        "Responda à pergunta abaixo usando apenas o contexto fornecido. "
        "Se o contexto não for suficiente, diga que não há informação "
        "suficiente.\n\n"
        f"Contexto:\n{context_text}\n\nPergunta: {question}"
    )

    chat_model = _build_chat_model()
    try:
        response = chat_model.invoke(prompt)
        answer = (
            response.content.strip()
            if hasattr(response, "content")
            else str(response).strip()
        )
    except Exception as exc:
        raise RuntimeError(
            f"Erro ao gerar a resposta final com o Ollama: {exc}"
        ) from exc

    return {"resposta": answer, "fontes": doc_ids}
