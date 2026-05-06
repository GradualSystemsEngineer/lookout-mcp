# Lookout MCP

Lookout is an offline mock MCP server for a Tableau-inspired internal BI platform.
The primary deliverable for this take-home assignment is the technical specification in
`docs/technical-spec.md`; the Python package is a small reference implementation that proves the
shape of the design.

## Scope

Lookout is intentionally local-only. It uses SQLite for persistent state and the local filesystem
for generated renders, exports, and cache files. It does not connect to Tableau, a warehouse, an
LLM API, an auth provider, or any external write-through system.

## Local Setup

Prerequisites:

- Python 3.12
- `make`

Create a virtual environment and install dependencies:

```bash
make install
```

Create a local environment file:

```bash
cp .env.example .env
```

Run quality checks:

```bash
make lint
make typecheck
make test
make smoke
```

Run the placeholder seed command:

```bash
make seed
```

Start the MCP server:

```bash
make run
```

## Current Tool Surface

The bootstrap phase exposes a single `health_check` tool. Later phases will add the full
agent-facing BI workflow: content discovery, datasource inspection, workbook/view access, bounded
queries, period comparison, deterministic renders, and exports.

## Repository Layout

- `docs/technical-spec.md`: primary assignment artifact.
- `docs/engineering-decisions.md`: rationale behind architecture and implementation choices.
- `src/lookout_mcp/`: Python package for the reference MCP server.
- `migrations/`: future SQLite migration files.
- `scripts/`: local utility scripts.
- `tests/`: pytest suite.
- `data/`: deterministic seed data inputs in later phases.
- `var/`: local generated files, ignored except for directory placeholders.

## Development Commands

- `make lint`: run Ruff checks.
- `make format`: format Python files with Ruff.
- `make test`: run pytest.
- `make typecheck`: run mypy.
- `make seed`: run the bootstrap seed command.
- `make run`: start the MCP server.
- `make smoke`: run a local smoke check without an MCP client.

