---
name: python-style
description: Use when Python work is present and you need hack-ink mandatory Python conventions.
---

# Python Style (hack-ink)

## Overview

Mandatory conventions for Python services, libraries, and tooling when Python is in scope.

## Scope

- These rules apply to Python services, libraries, and tooling in this repository when Python code or Python tooling is present.
- Do not apply them to non-Python projects.

## When to use

- You are about to run, modify, or add Python code or Python tooling (Poetry, scripts, CI helpers).
- You need a consistent virtualenv/Poetry workflow across multiple Python projects in one repo.

## Tooling and workflow (required)

- Use the shared workspace virtual environment at the repository root.
- Activate the shared environment before running Poetry commands.
- Do not create per-project virtual environments or project-local Poetry virtualenv overrides.

Setup:

- From the repository root, create the shared environment: `python -m venv .venv`.
- Activate the environment for your shell.
- From the relevant Python project directory, run `poetry sync --with dev`.

## Quick reference

- Create shared venv: `python -m venv .venv`
- Activate venv: (shell-specific)
- Sync deps: `poetry sync --with dev`

## Common mistakes

- Creating a per-project venv (hard to keep consistent in multi-project repos).
- Running Poetry without the shared venv activated (confusing tool resolution and caches).

## Outputs

Return evidence for:

- Virtual environment source and activation approach used.
- Poetry sync workflow steps executed.
