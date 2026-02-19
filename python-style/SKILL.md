---
name: python-style
description: Use when Python work is present and you need hack-ink mandatory Python conventions.
---

# Python Development Style Guide

These rules are hack-ink mandatory conventions for Python services, libraries, and Python tooling in this repository when Python is present.

## Scope

- These rules apply to Python services, libraries, and tooling in this repository when Python code or Python tooling is present.
- Do not apply them to non-Python projects.

## Tooling and workflow

- Use the shared workspace virtual environment at the repository root.
- Activate the shared environment before running Poetry commands.
- Do not create per-project virtual environments or project-local Poetry virtualenv overrides.

Setup:

- From the repository root, create the shared environment: `python -m venv .venv`.
- Activate the environment for your shell.
- From the relevant Python project directory, run `poetry sync --with dev`.

## Outputs

Return evidence for:

- Virtual environment source and activation approach used.
- Poetry sync workflow steps executed.
