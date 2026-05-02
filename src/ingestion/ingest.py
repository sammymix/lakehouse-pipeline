import requests
import psycopg2
import json
from datetime import datetime
import os

# Connection to the PostgreSQL database
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="lakehouse",
    user="lakehouse",
    password="lakehouse"
)
cur = conn.cursor()

# Create the bronze schema and the documents table if they don't exist
cur.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
conn.commit()  # commit the schema before creating the table inside it

cur.execute("""
    CREATE TABLE IF NOT EXISTS bronze.crypto_prices_raw (
        id SERIAL PRIMARY KEY,
        ingested_at TIMESTAMP DEFAULT NOW(),
        coin_id TEXT,
        raw_data JSONB
    );
""")
conn.commit()

# Pull data from CoinGecko API- top 10 coins by market cap, no API key needed.
url = "https://api.coingecko.com/api/v3/coins/markets"
params = {
    "vs_currency": "usd",
    "order": "market_cap_desc",
    "per_page": 10,
    "page": 1
}
response = requests.get(url, params=params)
response.raise_for_status()
coins = response.json()

# Load each coin as a raw JSON row into the bronze table
for coin in coins:
    cur.execute("""
        INSERT INTO bronze.crypto_prices_raw (coin_id, raw_data)
        VALUES (%s, %s);
    """, (coin["id"], json.dumps(coin)))
conn.commit()
cur.close()
conn.close()

print(f"Ingested {len(coins)} coins into bronze.crypto_prices_raw at {datetime.now()}")
