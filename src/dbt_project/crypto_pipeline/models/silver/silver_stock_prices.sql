WITH ranked AS (
    SELECT
        ticker,
        ingested_at,
        (raw_data->>'current_price')::NUMERIC   AS current_price_usd,
        (raw_data->>'market_cap')::NUMERIC       AS market_cap_usd,
        (raw_data->>'volume')::NUMERIC           AS volume_24h,
        (raw_data->>'day_high')::NUMERIC         AS day_high_usd,
        (raw_data->>'day_low')::NUMERIC          AS day_low_usd,
        (raw_data->>'price_change_pct')::NUMERIC AS price_change_52w_pct,
        raw_data->>'name'                        AS company_name,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY ingested_at DESC) AS rn
    FROM {{ source('bronze', 'stock_prices_raw') }}
)
SELECT
    ticker, ingested_at, current_price_usd, market_cap_usd,
    volume_24h, day_high_usd, day_low_usd,
    price_change_52w_pct, company_name
FROM ranked
WHERE rn = 1
