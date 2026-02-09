"""Ingest knowledge-base markdown files into ChromaDB."""


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
    # TODO: Use DirectoryLoader + RecursiveCharacterTextSplitter
    pass


def embed_and_store(documents: list) -> None:
    """Embed document chunks and persist them in ChromaDB.

    Parameters
    ----------
    documents : list[Document]
        Pre-chunked documents to embed and store.
    """
    # TODO: Use OllamaEmbeddings + Chroma.from_documents with persist_directory
    pass


def ingest_kb() -> None:
    """End-to-end ingestion: load → chunk → embed → store.

    Reads configuration from ``app.config.settings``.
    """
    # TODO: Call load_and_chunk_documents then embed_and_store
    pass
