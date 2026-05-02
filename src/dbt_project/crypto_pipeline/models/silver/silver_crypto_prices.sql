WITH ranked AS (
    SELECT
        coin_id,
        ingested_at,
        (raw_data->>'current_price')::NUMERIC AS current_price_usd,
        (raw_data->>'market_cap')::NUMERIC AS market_cap_usd,
        (raw_data->>'total_volume')::NUMERIC AS volume_24h_usd,
        (raw_data->>'price_change_percentage_24h')::NUMERIC AS price_change_24h_pct,
        raw_data->>'name' AS coin_name,
        raw_data->>'symbol' AS symbol,
        ROW_NUMBER() OVER (PARTITION BY coin_id ORDER BY ingested_at DESC) AS rn
    FROM {{ source('bronze', 'crypto_prices_raw') }}
)
SELECT
    coin_id, ingested_at, current_price_usd, market_cap_usd,
    volume_24h_usd, price_change_24h_pct, coin_name, symbol
FROM ranked
WHERE rn = 1
