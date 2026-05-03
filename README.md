# 🏗️ Agentic Data Lakehouse

A production-structured data pipeline that ingests live crypto and stock market data, applies bronze/silver/gold transformations using dbt, and exposes a natural language query interface powered by GPT-4o-mini — ask questions in plain English, get answers from your real data.

---

## 🎯 What It Does

- Pulls **live data** from two APIs: CoinGecko (top 10 cryptocurrencies) and Yahoo Finance (top 10 S&P 500 companies)
- Stores raw data in a **bronze layer** (Postgres, unmodified JSON)
- Cleans, deduplicates, and types data in a **silver layer** (dbt models with window functions)
- Aggregates into a **gold layer** (cross-asset comparison — crypto vs stocks side by side)
- Answers **natural language questions** about the data via a FastAPI + GPT-4o-mini endpoint

**Example questions you can ask:**
```
"Which asset has the highest market cap?"
→ NVIDIA Corporation with ~$4.82 trillion

"Compare total market cap of crypto vs stocks"
→ Stocks: $26.46T | Crypto: $2.41T — stocks are 11x larger

"Which crypto had the biggest 24h price change?"
→ TRON with +1.45%
```

---

## 🏛️ Architecture

```
CoinGecko API          Yahoo Finance API
      │                       │
      ▼                       ▼
bronze.crypto_prices_raw   bronze.stock_prices_raw
      │     (raw JSON rows, Postgres)     │
      └──────────────┬────────────────────┘
                     ▼
            dbt transformations
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
silver.silver_crypto_prices   silver.silver_stock_prices
  (deduped, typed columns)    (deduped, typed columns)
          │                     │
          └──────────┬──────────┘
                     ▼
        silver.gold_asset_comparison
         (crypto + stocks unified,
          ranked by market cap)
                     │
                     ▼
              FastAPI /ask
                     │
              GPT-4o-mini
          (question → SQL → answer)
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Ingestion | Python, `requests`, `yfinance` |
| Storage | PostgreSQL 15 (Docker) |
| Transformation | dbt-core, dbt-postgres |
| Data quality | dbt tests (not_null, unique) |
| AI layer | OpenAI GPT-4o-mini, FastAPI |
| Infrastructure | Docker, Python venv |

---

## 🚀 How to Run It Locally

### Prerequisites
- macOS / Linux
- Python 3.11
- Docker Desktop
- An OpenAI API key

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/lakehouse-pipeline.git
cd lakehouse-pipeline
```

### 2. Set up Python environment
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install requests psycopg2-binary python-dotenv dbt-postgres yfinance fastapi uvicorn openai
```

### 3. Add your API key
```bash
echo "OPENAI_API_KEY=your_key_here" > .env
```

### 4. Start Postgres
```bash
docker compose up -d
```

### 5. Ingest live data
```bash
python src/ingestion/ingest.py
python src/ingestion/ingest_stocks.py
```

### 6. Run dbt transformations
```bash
cd src/dbt_project/crypto_pipeline
dbt run
dbt test
```

### 7. Start the AI query server
```bash
cd ../../../src/ai
uvicorn main:app --reload --port 8000
```

### 8. Ask a question
```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which asset has the highest market cap?"}' | python3 -m json.tool
```

---

## 📁 Project Structure

```
lakehouse-pipeline/
├── docker-compose.yml
├── .env                          ← API keys (never committed)
├── src/
│   ├── ingestion/
│   │   ├── ingest.py             ← CoinGecko ingestion
│   │   └── ingest_stocks.py      ← Yahoo Finance ingestion
│   ├── dbt_project/
│   │   └── crypto_pipeline/
│   │       ├── models/
│   │       │   ├── sources.yml
│   │       │   ├── silver/
│   │       │   │   ├── silver_crypto_prices.sql
│   │       │   │   ├── silver_crypto_prices.yml  ← dbt tests
│   │       │   │   ├── silver_stock_prices.sql
│   │       │   │   └── silver_stock_prices.yml   ← dbt tests
│   │       │   └── gold/
│   │       │       ├── gold_crypto_summary.sql
│   │       │       └── gold_asset_comparison.sql
│   │       └── dbt_project.yml
│   └── ai/
│       ├── main.py               ← FastAPI server
│       └── query_engine.py       ← Text-to-SQL logic
```

---

## 💡 Key Engineering Decisions

**Why bronze/silver/gold layers?**
Raw data is always messy. The bronze layer preserves the original source exactly. Silver cleans and types it. Gold aggregates for business use. Each layer has a clear contract — if something breaks, you know exactly where to look.

**Why store raw JSON in bronze instead of typed columns?**
Schema evolution. When CoinGecko adds or removes a field, the bronze table doesn't break. You handle the change in your dbt model, not in your ingestion script.

**Why dbt instead of raw SQL scripts?**
dbt gives you version control, dependency graphs, built-in testing, and documentation for free. The `{{ ref() }}` and `{{ source() }}` syntax means dbt knows the order to run models and can detect breaking changes.

**Why two Claude/GPT calls instead of one for the AI layer?**
Separation of concerns. The first call only generates SQL — it's constrained and precise. The second call only explains results — it's conversational. Mixing both into one prompt makes each task harder for the model.

---

## 🧠 What I Learned

- **Python version matters for data tools** — dbt doesn't support Python 3.14 yet; pinning to 3.11 is the industry standard
- **Deduplication with window functions** — `ROW_NUMBER() OVER (PARTITION BY coin_id ORDER BY ingested_at DESC)` is the correct pattern for keeping only the latest record per entity
- **dbt schema vs Postgres schema** — dbt's default schema setting appends to your target schema, which is why gold models appeared in `silver_gold` instead of `gold`
- **Text-to-SQL prompting** — giving the model explicit schema context and strict output rules (no markdown, no explanation) produces reliable, runnable SQL
- **Debugging is the job** — every error in this project (`TIMESTAMP` syntax, schema doesn't exist, Python path issues, dotenv loading) is something real data engineers hit in production

---

## 🗺️ What's Next

- [ ] Streamlit chat UI (ask questions in a browser instead of curl)
- [ ] Scheduled ingestion with Prefect (run every hour automatically)
- [ ] Delta Lake bronze layer (versioned, time-travel capable storage)
- [ ] Apache Kafka for real-time streaming ingestion
- [ ] Terraform + CI/CD for cloud deployment

---

*Built by Samuel Jean Lys — M.S. Computer Science, Illinois Institute of Technology*
