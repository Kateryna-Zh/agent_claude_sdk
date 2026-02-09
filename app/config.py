"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Type-safe configuration sourced from .env / environment."""

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"

    # PostgreSQL
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "learning_assistant"
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    pg_pool_min: int = 1
    pg_pool_max: int = 5

    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "knowledge_base"

    # Tavily
    tavily_api_key: str = ""

    # Knowledge Base
    kb_dir: str = "./kb"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
