# 🏗️ Agentic Data Lakehouse

A production-grade data pipeline that ingests live crypto and stock market data every hour, applies bronze/silver/gold transformations using dbt, and exposes a natural language query interface powered by GPT-4o-mini — fully deployed on AWS.

---

## 🎯 What It Does

- Pulls **live data** from two APIs: CoinGecko (top 10 cryptocurrencies) and Yahoo Finance (top 10 S&P 500 companies)
- Stores raw data in a **bronze layer** (Amazon RDS Postgres, unmodified JSON)
- Cleans, deduplicates, and types data in a **silver layer** (dbt models with window functions)
- Aggregates into a **gold layer** (cross-asset comparison — crypto vs stocks side by side)
- Runs **automatically every hour** via AWS Lambda + EventBridge — no manual triggers needed
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
Every hour (Amazon EventBridge)
         │
         ├──────────────────────────────────┐
         ▼                                  ▼
AWS Lambda                          AWS Lambda
lakehouse-ingest-crypto         lakehouse-ingest-stocks
(CoinGecko API)                 (Yahoo Finance API)
         │                                  │
         ▼                                  ▼
bronze.crypto_prices_raw      bronze.stock_prices_raw
              (Amazon RDS Postgres — raw JSON rows)
         │                                  │
         └──────────────┬───────────────────┘
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

## ☁️ Cloud Infrastructure (AWS)

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| **Amazon RDS** (Postgres 15) | Managed database — always-on, no Docker needed | db.t3.micro, 20GB |
| **AWS Lambda** (x2) | Serverless ingestion — crypto + stocks functions | 1M requests/month |
| **Amazon EventBridge** | Hourly schedule that triggers both Lambda functions | 14M events/month |
| **Amazon S3** | Stores Lambda deployment packages | 5GB |
| **AWS Secrets Manager** | Secure API key storage | 30-day free trial |
| **IAM** | Least-privilege roles for Lambda execution | Always free |

**Deployment region:** `us-east-1`

---

## 🛠️ Tech Stack

| Layer | Local | AWS |
|-------|-------|-----|
| Ingestion | Python, `requests` | AWS Lambda |
| Scheduling | Prefect (local) | Amazon EventBridge |
| Storage | PostgreSQL in Docker | Amazon RDS Postgres 15 |
| Transformation | dbt-core, dbt-postgres | dbt (runs locally against RDS) |
| Data quality | dbt tests (not_null, unique) | dbt tests |
| AI layer | OpenAI GPT-4o-mini, FastAPI | OpenAI GPT-4o-mini, FastAPI |
| Secrets | `.env` file | AWS Secrets Manager |

---

## 🚀 How to Run It Locally (against AWS RDS)

### Prerequisites
- macOS / Linux
- Python 3.11
- Docker Desktop
- AWS account + AWS CLI configured
- OpenAI API key

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/lakehouse-pipeline.git
cd lakehouse-pipeline
```

### 2. Set up Python environment
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install requests psycopg2-binary python-dotenv dbt-postgres fastapi uvicorn openai
```

### 3. Configure environment variables
```bash
cp .env.example .env
# Fill in your values in .env:
# OPENAI_API_KEY=sk-...
# DB_HOST=your-rds-endpoint.us-east-1.rds.amazonaws.com
# DB_PORT=5432
# DB_NAME=lakehouse
# DB_USER=lakehouse
# DB_PASSWORD=your-password
```

### 4. Run ingestion manually
```bash
python src/ingestion/ingest.py
python src/ingestion/ingest_stocks.py
```

### 5. Run dbt transformations
```bash
cd src/dbt_project/crypto_pipeline
dbt run
dbt test
```

### 6. Start the AI query server
```bash
cd src/ai
uvicorn main:app --reload --port 8000
```

### 7. Ask a question
```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which asset has the highest market cap?"}' | python3 -m json.tool
```

---

## ☁️ AWS Deployment Guide

### Prerequisites
- AWS CLI installed and configured (`aws configure`)
- IAM user with: RDS, Lambda, EventBridge, S3, SecretsManager, IAM, EC2 permissions

### 1. Store your API key securely
```bash
aws secretsmanager create-secret \
  --name "lakehouse/openai-api-key" \
  --secret-string '{"OPENAI_API_KEY":"your-key-here"}'
```

### 2. Create RDS Postgres instance
```bash
aws rds create-db-instance \
  --db-instance-identifier lakehouse-postgres \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15 \
  --master-username lakehouse \
  --master-user-password your-password \
  --allocated-storage 20 \
  --db-name lakehouse \
  --publicly-accessible \
  --no-multi-az \
  --storage-type gp2
```

### 3. Create Lambda execution role
```bash
aws iam create-role \
  --role-name lakehouse-lambda-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]
  }'

aws iam attach-role-policy --role-name lakehouse-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam attach-role-policy --role-name lakehouse-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
```

### 4. Package and deploy Lambda functions
```bash
# Build Linux-compatible packages — IMPORTANT: exclude macOS metadata
mkdir -p lambda_build/crypto
pip install psycopg2-binary requests \
  --target lambda_build/crypto \
  --platform manylinux2014_x86_64 \
  --implementation cp --python-version 3.11 --only-binary=:all:

cp src/lambda/ingest_crypto.py lambda_build/crypto/lambda_function.py

cd lambda_build/crypto
zip -r ../crypto_lambda.zip . \
  --exclude "*.DS_Store" --exclude "*__MACOSX*" \
  --exclude "*.pyc" --exclude "*__pycache__*"

aws lambda create-function \
  --function-name lakehouse-ingest-crypto \
  --runtime python3.11 \
  --role YOUR_ROLE_ARN \
  --handler lambda_function.handler \
  --zip-file fileb://../crypto_lambda.zip \
  --timeout 60 --memory-size 256 \
  --environment "Variables={DB_HOST=YOUR_RDS_ENDPOINT,DB_PASSWORD=your-password}"
```

### 5. Schedule hourly runs with EventBridge
```bash
aws events put-rule \
  --name "lakehouse-hourly-trigger" \
  --schedule-expression "rate(1 hour)" \
  --state ENABLED

aws events put-targets \
  --rule "lakehouse-hourly-trigger" \
  --targets '[
    {"Id": "crypto-target", "Arn": "YOUR_CRYPTO_LAMBDA_ARN"},
    {"Id": "stocks-target", "Arn": "YOUR_STOCKS_LAMBDA_ARN"}
  ]'
```

---

## 📁 Project Structure

```
lakehouse-pipeline/
├── docker-compose.yml            ← Local Postgres (for development)
├── .env.example                  ← Environment variable template
├── .gitignore                    ← Excludes .env, venv/, target/
├── src/
│   ├── ingestion/
│   │   ├── ingest.py             ← CoinGecko ingestion (local)
│   │   └── ingest_stocks.py      ← Yahoo Finance ingestion (local)
│   ├── lambda/
│   │   ├── ingest_crypto.py      ← Lambda handler — crypto
│   │   └── ingest_stocks.py      ← Lambda handler — stocks (direct HTTP)
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
│   ├── ai/
│   │   ├── main.py               ← FastAPI server
│   │   └── query_engine.py       ← Text-to-SQL logic
│   └── pipeline_flow.py          ← Prefect flow (local orchestration)
```

---

## 💡 Key Engineering Decisions

**Why bronze/silver/gold layers?**
Raw data is always messy. The bronze layer preserves the original source exactly. Silver cleans and types it. Gold aggregates for business use. Each layer has a clear contract — if something breaks, you know exactly where to look.

**Why store raw JSON in bronze instead of typed columns?**
Schema evolution. When CoinGecko adds or removes a field, the bronze table doesn't break. You handle the change in your dbt model, not in your ingestion script.

**Why Lambda instead of a long-running server?**
Lambda costs nothing when not running and scales automatically. For hourly ingestion jobs that complete in under 60 seconds, serverless is the right tool — a persistent server would cost money 24/7 for no reason.

**Why direct HTTP calls instead of yfinance in Lambda?**
`yfinance` pulls in pandas and numpy, making the Lambda package 300MB+ — over AWS's 262MB unzipped limit. Direct HTTP calls to Yahoo Finance's API return the same data with zero extra dependencies.

**Why two GPT calls instead of one for the AI layer?**
Separation of concerns. The first call only generates SQL — constrained and precise. The second call only explains results — conversational. Mixing both into one prompt makes each task harder for the model and harder to debug.

**Why macOS metadata exclusion matters for Lambda zips?**
macOS adds hidden extended attributes to files. Without `--exclude "*.DS_Store"`, these inflate a 15MB package to 95MB and corrupt Linux binaries. Always build Lambda zips with explicit exclusions on Mac.

---

## 🧠 What I Learned

- **Python version matters for data tools** — dbt doesn't support Python 3.14; pinning to 3.11 is the industry standard
- **Deduplication with window functions** — `ROW_NUMBER() OVER (PARTITION BY coin_id ORDER BY ingested_at DESC)` is the correct pattern for keeping only the latest record per entity
- **Lambda packages must be built for Linux** — use `--platform manylinux2014_x86_64` when building on Mac, and always exclude macOS metadata from zips
- **Security group rules are per-source** — Lambda runs from AWS IP ranges, not your laptop's IP; opening port 5432 only to your laptop doesn't help Lambda connect
- **Text-to-SQL prompting** — giving the model explicit schema context and strict output rules (no markdown, no backticks) produces reliable, runnable SQL
- **Never commit .env** — `git rm --cached .env` removes a tracked file without deleting it locally; rotate any key that was ever pushed
- **Debugging is the job** — every error in this project was something real data engineers hit in production

---

## 🗺️ What's Next

- [ ] Streamlit chat UI (ask questions in a browser instead of curl)
- [ ] Deploy FastAPI AI endpoint to Lambda + API Gateway (public URL)
- [ ] Delta Lake bronze layer (versioned, time-travel capable storage)
- [ ] Apache Kafka for real-time streaming ingestion
- [ ] Terraform for infrastructure-as-code (reproduce entire AWS setup in one command)
- [ ] GitHub Actions CI/CD (auto-deploy Lambda on every push to main)

---

*Built by Samuel Jean Lys — M.S. Computer Science, Illinois Institute of Technology*
