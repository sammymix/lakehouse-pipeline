# Lakehouse Pipeline

## How to work on this project
See @README.md for commands, architecture, and setup.
See @src/dbt_project/crypto_pipeline/dbt_project.yml for dbt config.

## Python version
- Always use Python 3.11. Never suggest 3.12, 3.13, or 3.14 — dbt does not support them.

## Project structure
- Ingestion scripts: `src/ingestion/` (local) and `src/lambda/` (AWS Lambda handlers)
- dbt models: `src/dbt_project/crypto_pipeline/models/`
- AI layer: `src/ai/` only — never create AI-related files elsewhere
- Never create files directly in `src/` root

## Lambda — critical constraints
- Never use `yfinance` in `src/lambda/` — use direct HTTP to Yahoo Finance only
- Lambda zips must always include: --exclude "*.DS_Store" --exclude "*__MACOSX*"
- Never import pandas or numpy in Lambda functions — 262MB unzipped package limit
- Build with: --platform manylinux2014_x86_64 --python-version 3.11

## Data layer rules
- Bronze layer: raw JSONB only, append-only, never parse or type at ingestion
- Silver deduplication: always ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ingested_at DESC)
- Never add typed columns to bronze ingestion scripts

## AI layer rules
- Always two separate GPT-4o-mini calls: one for SQL generation, one for explanation
- Never combine into a single prompt
- SQL generation output: no markdown, no backticks, raw SQL only
- The schema context in `query_engine.py:16` is the source of truth — keep it in sync with dbt models
- `query_engine.py` currently hardcodes localhost — always use env vars when pointing at RDS

## dbt
- Profile name: `crypto_pipeline` — lives in ~/.dbt/profiles.yml, not in the repo
- Gold models live in the `silver` schema in Postgres due to dbt prefix behavior — this is intentional

## Secrets
- Local: .env file — never commit it
- AWS: Secrets Manager — never hardcode credentials in Lambda functions

## Hooks — learned in practice
- Claude Code passes tool data via stdin as JSON, NOT environment variables — $CLAUDE_TOOL_INPUT_PATH does not exist
- Extract fields from stdin using Python + json.loads(), not jq or re.search — stdin JSON contains literal newlines that break jq
- ruff path: $(git rev-parse --show-toplevel)/venv/bin/ruff — resolved at runtime, works on any machine
- ruff requires --unsafe-fixes to auto-remove unused imports (F401)
- Hook pattern that works: pipe stdin to python3 -c to parse JSON and extract the needed field, then act on it
- PreToolUse blocks use exit 2 to signal Claude Code to cancel the tool call
