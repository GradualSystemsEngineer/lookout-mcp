# Lookout MCP Agent Instructions

## Project Context

Lookout is an offline mock MCP server for a Tableau-inspired internal BI platform. The primary
deliverable is `docs/technical-spec.md`; the Python implementation is a reference implementation
that proves the spec.

AI agents use Lookout through MCP tools. Lookout itself must not call an LLM or require API keys.
The system runs locally, stores persistent state in SQLite, and writes generated renders, exports,
and cache files under `LOOKOUT_FS_ROOT`.

Out of scope:

- Real Tableau integration
- Real data warehouse integration
- Auth, users, or multi-tenancy
- Real-time updates
- External write-through
- Network services required for tests

## Execution Rules

- Keep the technical specification as the source of truth.
- Keep implementation behavior aligned with the spec.
- Follow the phased prompt sequence in `lookout_codex_prompts/`.
- Do not implement later-phase features while working an earlier phase unless the user explicitly
  asks for that phase.
- Every phase should leave the repository working and testable.
- Prefer boring, maintainable technology over clever abstractions.
- Favor deterministic offline behavior.

## Stack

- Python 3.12
- Official MCP Python SDK / FastMCP
- SQLite through the Python standard library
- Pydantic for schemas and validation
- pytest for tests
- Ruff for linting and formatting
- mypy for type checking
- Local filesystem directories under `var/` for generated artifacts

## Commands

Use these commands from the repository root:

```bash
make install
make lint
make format
make typecheck
make test
make seed
make smoke
make run
```

For normal verification after code changes, run:

```bash
make lint
make typecheck
make test
make smoke
```

Docs-only changes do not require the full suite unless they alter documented commands or behavior.

## Coding Standards

- Keep modules small and clearly named.
- Separate domain logic from MCP transport code.
- Use Pydantic models for tool inputs and outputs.
- Return JSON-serializable structured data from tool functions.
- Use the standard error envelope:

```json
{"error": {"code": "...", "message": "...", "details": {}}}
```

- Validate IDs, pagination, filters, sorts, query limits, and filesystem paths before use.
- Never write generated files outside `LOOKOUT_FS_ROOT`.
- Avoid unbounded result sets or verbose list responses.
- Prefer exports over returning large row sets inline.

## Documentation Standards

Update `docs/technical-spec.md` whenever behavior, tool contracts, schemas, errors, seed strategy,
or workflow semantics change.

Update `README.md` when setup, commands, repository layout, or supported flows change.

Use `docs/engineering-decisions.md` for durable rationale and tradeoffs that are useful in a
follow-up technical interview.

## Testing Standards

- Use temporary SQLite databases and filesystem roots in tests.
- Keep tests deterministic and independent of ordering.
- Cover happy paths, validation errors, source degradation, token-safety limits, and generated file
  behavior as those features are added.
- Do not require external services, network access, or API keys.

## Git Workflow

- Commit completed work without waiting for an explicit reminder, unless the user asks not to.
- Keep commits focused on a coherent phase or behavior slice.
- Use conventional commit messages unless a more specific repo convention is introduced.
- Do not include `.env`, virtualenvs, generated cache files, or local SQLite databases in commits.
- Do not rewrite or discard user changes without explicit permission.

