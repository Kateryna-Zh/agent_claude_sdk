# LangGraph

# LangGraph Overview

LangGraph is a framework built on top of LangChain for **stateful, multi-agent workflows**.

It is designed for:
- complex logic
- branching
- loops
- multi-agent systems

## Core Idea

Instead of linear chains, LangGraph uses **graphs**:
- nodes = steps or agents
- edges = transitions
- state = shared data structure

## Key Concepts

### State
A typed object shared between nodes.

Example fields:
- user_message
- retrieved_context
- db_results
- final_answer

### Nodes
Pure functions or agent calls that:
- read state
- modify state
- return updated state

### Edges
Define how execution flows:
- unconditional
- conditional
- looping

### Routers
Special nodes that decide **what happens next** based on state.

Example:
- if intent == "quiz" → QuizAgent
- if intent == "plan" → PlannerAgent

## Why LangGraph over LangChain?

LangChain:
- good for linear flows

LangGraph:
- explicit control
- easier debugging
- better for multi-agent apps
- safer execution

## Typical Use Cases

- Personal assistants
- Multi-agent RAG
- AI copilots
- Workflow automation
- Decision trees

## Example Pattern

1. Router node
2. Optional RAG retrieval
3. Optional web search
4. Specialist agent
5. DB write
6. Final response

## Strengths
- Deterministic flow
- Explicit logic
- Easier testing
- Better production readiness

## When to Use LangGraph
- More than one agent
- Multiple tools
- Conditional logic
- Stateful conversations
