SELECT
    COUNT(DISTINCT coin_id)              AS total_coins_tracked,
    ROUND(AVG(current_price_usd), 2)    AS avg_price_usd,
    SUM(market_cap_usd)                 AS total_market_cap_usd,
    SUM(volume_24h_usd)                 AS total_volume_24h_usd,
    MAX(current_price_usd)              AS highest_price_usd,
    MIN(current_price_usd)              AS lowest_price_usd,
    MAX(ingested_at)                    AS last_ingested_at
FROM {{ ref('silver_crypto_prices') }}
