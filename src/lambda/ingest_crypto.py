import boto3
import json
import requests
import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.environ['DB_HOST'],
        port=5432,
        dbname='lakehouse',
        user='lakehouse',
        password=os.environ['DB_PASSWORD']
    )

def handler(event, context):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bronze.crypto_prices_raw (
            id SERIAL PRIMARY KEY,
            ingested_at TIMESTAMP DEFAULT NOW(),
            coin_id TEXT,
            raw_data JSONB
        );
    """)
    conn.commit()
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 10, "page": 1}
    coins = requests.get(url, params=params).json()
    for coin in coins:
        cur.execute(
            "INSERT INTO bronze.crypto_prices_raw (coin_id, raw_data) VALUES (%s, %s)",
            (coin["id"], json.dumps(coin))
        )
    conn.commit()
    cur.close()
    conn.close()
    return {"statusCode": 200, "body": f"Loaded {len(coins)} coins"}
