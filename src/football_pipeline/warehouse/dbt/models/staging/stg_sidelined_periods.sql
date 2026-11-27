-- One row per absence period, from the latest answer about each player.
{{ config(materialized='table', engine='MergeTree', order_by='player_id') }}

SELECT DISTINCT
    player_id,
    JSONExtractString(period, 'type') AS type,
    toDate32OrNull(JSONExtractString(period, 'start')) AS start_date,
    toDate32OrNull(JSONExtractString(period, 'end')) AS end_date,
    loaded_at AS ingested_at
FROM {{ ref('stg_sidelined_players') }}
ARRAY JOIN JSONExtractArrayRaw(periods) AS period
