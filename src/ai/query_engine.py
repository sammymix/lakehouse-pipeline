import logging
from openai import OpenAI
import psycopg2
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)

# ── 0. Startup check — fail fast if required env vars are missing ─────────────
_REQUIRED_ENV = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "OPENAI_API_KEY", "API_KEY"]
_missing = [v for v in _REQUIRED_ENV if not os.getenv(v)]
if _missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(_missing)}")

# ── 1. Module-level OpenAI client (one instance, not one per request) ─────────
_openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── 2. Database connection ────────────────────────────────────────────────────
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

# ── 3. Schema context we give the model so it knows what tables exist ─────────
SCHEMA_CONTEXT = """
You are a data analyst assistant. You have access to a Postgres database with these views:

silver.silver_crypto_prices:
  - coin_id TEXT (e.g. 'bitcoin', 'ethereum')
  - coin_name TEXT (e.g. 'Bitcoin')
  - symbol TEXT (e.g. 'btc')
  - current_price_usd NUMERIC
  - market_cap_usd NUMERIC
  - volume_24h_usd NUMERIC
  - price_change_24h_pct NUMERIC
  - ingested_at TIMESTAMP

silver.silver_stock_prices:
  - ticker TEXT (e.g. 'AAPL', 'NVDA')
  - company_name TEXT
  - current_price_usd NUMERIC
  - market_cap_usd NUMERIC
  - volume_24h NUMERIC
  - day_high_usd NUMERIC
  - day_low_usd NUMERIC
  - price_change_52w_pct NUMERIC
  - ingested_at TIMESTAMP

silver.gold_asset_comparison:
  - asset_name TEXT
  - asset_ticker TEXT
  - asset_class TEXT ('crypto' or 'stock')
  - current_price_usd NUMERIC
  - market_cap_usd NUMERIC
  - market_cap_billions NUMERIC
  - volume NUMERIC
  - price_change_pct NUMERIC

Rules:
- Return ONLY a valid SQL SELECT statement, nothing else
- No markdown, no explanation, no backticks
- Always use schema-qualified table names (e.g. silver.gold_asset_comparison)
- LIMIT results to 20 rows maximum
"""

# ── 4. SQL validation — block anything that isn't a plain SELECT ──────────────
_FORBIDDEN_KEYWORDS = {
    "drop", "insert", "update", "delete", "alter", "truncate",
    "copy", "execute", "do", "call", "grant", "create",
    "pg_read_file", "pg_write_file", "pg_ls_dir",
}

def validate_sql(sql: str) -> None:
    """Raise ValueError if sql is not a safe, single SELECT statement."""
    normalized = sql.strip().lower()
    if not normalized.startswith("select"):
        raise ValueError("SQL must start with SELECT")
    if ";" in normalized:
        raise ValueError("SQL must not contain semicolons")
    for kw in _FORBIDDEN_KEYWORDS:
        if kw in f" {normalized} ":
            raise ValueError(f"SQL contains forbidden keyword: {kw.upper()}")

# ── 5. Convert question → SQL using GPT-4o-mini ───────────────────────────────
def question_to_sql(question: str) -> str:
    response = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=500,
        messages=[
            {"role": "system", "content": SCHEMA_CONTEXT},
            {"role": "user", "content": f"Question: {question}\n\nSQL:"}
        ]
    )
    return response.choices[0].message.content.strip()

# ── 6. Run the SQL against Postgres (read-only session) ───────────────────────
def run_sql(sql: str) -> tuple[list, list]:
    validate_sql(sql)
    conn = None
    try:
        conn = get_db_connection()
        conn.set_session(readonly=True)
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        return columns, rows
    except psycopg2.Error as exc:
        logger.error("Database error: %s", exc)
        raise RuntimeError("query failed") from exc
    finally:
        if conn is not None:
            conn.close()

# ── 7. Summarize results in plain English using GPT-4o-mini ──────────────────
def summarize_results(question: str, sql: str, columns: list, rows: list) -> str:
    results_text = f"Columns: {columns}\nRows: {rows[:10]}"
    response = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=300,
        messages=[
            {"role": "user", "content": f"""The user asked: "{question}"
The SQL that ran: {sql}
The results: {results_text}

Give a clear 2-3 sentence answer in plain English. Be specific with numbers."""}
        ]
    )
    return response.choices[0].message.content.strip()
