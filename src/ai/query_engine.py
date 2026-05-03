from openai import OpenAI
import psycopg2
import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# ── 1. Database connection ────────────────────────────────────────────────────
def get_db_connection():
    return psycopg2.connect(
        host="localhost", port=5432,
        dbname="lakehouse", user="lakehouse", password="lakehouse"
    )

# ── 2. Schema context we give Claude so it knows what tables exist ────────────
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

# ── 3. Convert question → SQL using Claude ────────────────────────────────────
def question_to_sql(question: str) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=500,
        messages=[
            {"role": "system", "content": SCHEMA_CONTEXT},
            {"role": "user", "content": f"Question: {question}\n\nSQL:"}
        ]
    )
    return response.choices[0].message.content.strip()
# ── 4. Run the SQL against your real Postgres data ────────────────────────────
def run_sql(sql: str) -> tuple[list, list]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(sql)
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return columns, rows

# ── 5. Summarize results in plain English using Claude ────────────────────────
def summarize_results(question: str, sql: str, columns: list, rows: list) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    results_text = f"Columns: {columns}\nRows: {rows[:10]}"
    response = client.chat.completions.create(
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