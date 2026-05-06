# Engineering Decisions

## Stack

Lookout uses Python 3.12, the official MCP Python SDK/FastMCP, SQLite, Pydantic, pytest, Ruff, and
mypy. This is a boring local stack that keeps the take-home easy to run while still exercising the
important MCP contract and BI workflow decisions.

## Offline-first design

The mock server has no external dependencies at runtime. SQLite represents persistent state and the
local filesystem stores generated artifacts. This keeps tests deterministic and avoids hiding design
quality behind external services.

## Specification-first implementation

The technical specification is the primary deliverable. The reference implementation should stay
small and aligned with that spec, proving tool contracts and failure modes without overbuilding a
full BI product.

## MCP boundary

Lookout does not call an LLM. Its job is to expose useful, bounded, token-efficient tools to an
external AI agent. Tool descriptions, schemas, pagination, warnings, and error envelopes are part of
the product surface.

