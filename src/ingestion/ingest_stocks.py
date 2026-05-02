import yfinance as yf
import psycopg2
import json
from datetime import datetime

conn = psycopg2.connect(
    host="localhost", port=5432,
    dbname="lakehouse", user="lakehouse", password="lakehouse"
)
cur = conn.cursor()

# Create bronze table for stocks
cur.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
conn.commit()

cur.execute("""
    CREATE TABLE IF NOT EXISTS bronze.stock_prices_raw (
        id SERIAL PRIMARY KEY,
        ingested_at TIMESTAMP DEFAULT NOW(),
        ticker TEXT,
        raw_data JSONB
    );
""")
conn.commit()

# Top 10 S&P 500 companies by market cap
tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "LLY", "AVGO", "TSLA"]

for ticker in tickers:
    stock = yf.Ticker(ticker)
    info = stock.info

    # Pull only the fields we care about
    row = {
        "ticker":         ticker,
        "name":           info.get("longName"),
        "current_price":  info.get("currentPrice"),
        "market_cap":     info.get("marketCap"),
        "volume":         info.get("volume"),
        "day_high":       info.get("dayHigh"),
        "day_low":        info.get("dayLow"),
        "price_change_pct": info.get("52WeekChange")
    }

    cur.execute(
        "INSERT INTO bronze.stock_prices_raw (ticker, raw_data) VALUES (%s, %s)",
        (ticker, json.dumps(row))
    )
    print(f"Loaded {ticker} — ${row['current_price']}")

conn.commit()
cur.close()
conn.close()
print(f"\nDone. Loaded {len(tickers)} stocks at {datetime.now()}")