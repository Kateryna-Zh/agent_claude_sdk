# LangChain

# LangChain Overview

LangChain is a Python framework for building applications powered by Large Language Models (LLMs).
It focuses on **orchestration**, not model training.

## Core Idea

LangChain helps you connect:
- LLMs
- prompts
- memory
- tools (databases, APIs, search)
- retrieval systems (RAG)

into reusable and testable components.

## Key Concepts

### LLM Wrappers
Abstractions over model providers (OpenAI, Ollama, Azure OpenAI, etc.).

Example:
- ChatOpenAI
- OllamaLLM

### Prompts
Reusable prompt templates with variables.

Example:
- PromptTemplate
- ChatPromptTemplate

### Chains
Predefined or custom sequences of steps.

Examples:
- LLMChain
- RetrievalQA
- ConversationalRetrievalChain

### Memory
State across conversations.

Common types:
- ConversationBufferMemory
- ConversationSummaryMemory
- ConversationBufferWindowMemory

### Tools
Functions the LLM can call.

Examples:
- SQL execution
- Web search
- File system access
- Custom Python functions

### Retrievers
Components that fetch relevant context for RAG.

Examples:
- VectorStoreRetriever
- MultiQueryRetriever

## RAG in LangChain

Typical RAG flow:
1. User query
2. Embed query
3. Retrieve similar chunks
4. Inject context into prompt
5. Generate answer

LangChain does **not** enforce where vectors live:
- Chroma
- FAISS
- pgvector
- Pinecone

## Strengths
- Fast prototyping
- Huge ecosystem
- Good abstractions
- Works well with tools

## Limitations
- Chains can become hard to debug
- Less explicit control than LangGraph
- Complex flows get messy

## When to Use LangChain
- Simple assistants
- RAG applications
- Tool-using agents
- Rapid experimentation
