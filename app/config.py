"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Type-safe configuration sourced from .env / environment."""

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout_seconds: int = 30
    chat_timeout_seconds: int = 15
    db_tool_timeout_seconds: int = 4

    # PostgreSQL
    pg_host: str = "localhost"
    pg_port: int = 5433
    pg_database: str = "learning_assistant"
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    pg_pool_min: int = 1
    pg_pool_max: int = 5

    # Database backend
    db_backend: str = "mcp"  # mcp | psycopg2

    # MCP (pg-mcp-server)
    mcp_server_command: str = "npx"
    mcp_server_args: str = "--yes pg-mcp-server --transport stdio"
    mcp_database_url: str = ""
    mcp_allow_write_ops: bool = False
    mcp_tool_name: str = "query"
    mcp_query_key: str = "sql"
    mcp_params_key: str = "params"
    mcp_supports_params: bool = False
    mcp_fallback_to_psycopg2: bool = True

    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "knowledge_base"

    # Tavily
    tavily_api_key: str = ""

    # Knowledge Base
    kb_dir: str = "./kb"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
