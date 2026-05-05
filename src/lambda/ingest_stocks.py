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

def get_stock_data(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, params={"interval": "1d", "range": "1d"}, timeout=10)
    meta = r.json()["chart"]["result"][0]["meta"]
    return {
        "ticker": ticker,
        "current_price": meta.get("regularMarketPrice"),
        "market_cap": meta.get("marketCap"),
        "volume": meta.get("regularMarketVolume"),
        "day_high": meta.get("regularMarketDayHigh"),
        "day_low": meta.get("regularMarketDayLow"),
        "name": meta.get("longName") or ticker
    }

def handler(event, context):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bronze.stock_prices_raw (
            id SERIAL PRIMARY KEY,
            ingested_at TIMESTAMP DEFAULT NOW(),
            ticker TEXT,
            raw_data JSONB
        );
    """)
    conn.commit()
    tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
               "META", "BRK-B", "LLY", "AVGO", "TSLA"]
    loaded = 0
    for ticker in tickers:
        try:
            row = get_stock_data(ticker)
            cur.execute(
                "INSERT INTO bronze.stock_prices_raw (ticker, raw_data) VALUES (%s, %s)",
                (ticker, json.dumps(row))
            )
            loaded += 1
        except Exception as e:
            print(f"Failed {ticker}: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return {"statusCode": 200, "body": f"Loaded {loaded} stocks"}
