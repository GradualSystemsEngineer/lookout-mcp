.PHONY: install lint format test typecheck seed run smoke ui-install ui-api ui-dev ui-test

PYTHON ?= python3.12

ifneq (,$(wildcard .env))
include .env
export
endif

install:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e ".[dev]"

lint:
	.venv/bin/python -m ruff check .

format:
	.venv/bin/python -m ruff format .

test:
	.venv/bin/python -m pytest

typecheck:
	.venv/bin/python -m mypy

seed:
	.venv/bin/python -m lookout_mcp.db seed

run:
	.venv/bin/python -m lookout_mcp.server

smoke:
	.venv/bin/python scripts/smoke.py

ui-install:
	npm --prefix ui install

ui-api:
	.venv/bin/python -m lookout_mcp.demo_ui

ui-dev:
	npm --prefix ui run dev

ui-test:
	npm --prefix ui test
