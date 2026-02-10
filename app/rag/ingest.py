"""Ingest knowledge-base markdown files into ChromaDB."""

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from app.config import settings
from app.llm.ollama_client import get_embeddings


def load_and_chunk_documents(kb_dir: str) -> list:
    """Load all markdown files from *kb_dir* and split into chunks.

    Parameters
    ----------
    kb_dir : str
        Path to the knowledge-base directory.

    Returns
    -------
    list[langchain_core.documents.Document]
        Chunked documents ready for embedding.
    """
    loader = DirectoryLoader(
        kb_dir,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True,
    )
    documents = loader.load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    return splitter.split_documents(documents)


def embed_and_store(documents: list) -> None:
    """Embed document chunks and persist them in ChromaDB.

    Parameters
    ----------
    documents : list[Document]
        Pre-chunked documents to embed and store.
    """
    embeddings = get_embeddings()
    chroma = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=settings.chroma_persist_dir,
        collection_name=settings.chroma_collection,
    )
    if hasattr(chroma, "persist"):
        chroma.persist()


def ingest_kb() -> None:
    """End-to-end ingestion: load → chunk → embed → store.

    Reads configuration from ``app.config.settings``.
    """
    documents = load_and_chunk_documents(settings.kb_dir)
    print(f"INGEST: loaded {len(documents)} chunks", flush=True)
    if not documents:
        return
    embed_and_store(documents)
    try:
        chroma = Chroma(
            collection_name=settings.chroma_collection,
            persist_directory=settings.chroma_persist_dir,
            embedding_function=get_embeddings(),
        )
        count = chroma._collection.count()  # type: ignore[attr-defined]
        print(f"INGEST: collection '{settings.chroma_collection}' count={count}", flush=True)
    except Exception:
        print("INGEST: unable to read collection count", flush=True)
