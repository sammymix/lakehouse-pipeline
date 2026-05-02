-- Compare crypto vs stocks side by side
-- This is the kind of model an analyst would query directly

WITH crypto AS (
    SELECT
        coin_name        AS asset_name,
        symbol           AS asset_ticker,
        current_price_usd,
        market_cap_usd,
        volume_24h_usd   AS volume,
        price_change_24h_pct AS price_change_pct,
        'crypto'         AS asset_class
    FROM {{ ref('silver_crypto_prices') }}
),

stocks AS (
    SELECT
        company_name     AS asset_name,
        ticker           AS asset_ticker,
        current_price_usd,
        market_cap_usd,
        volume_24h       AS volume,
        price_change_52w_pct AS price_change_pct,
        'stock'          AS asset_class
    FROM {{ ref('silver_stock_prices') }}
)

SELECT * FROM crypto
UNION ALL
SELECT * FROM stocks
ORDER BY market_cap_usd DESC
