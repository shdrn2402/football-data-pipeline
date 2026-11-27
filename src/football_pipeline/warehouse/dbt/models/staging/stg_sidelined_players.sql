-- Players whose absences were requested. A player listed here without periods has
-- no known absence; a player not listed is unknown.
{{ config(materialized='table', engine='MergeTree', order_by='player_id') }}

SELECT
    player_id,
    argMax(periods, ingested_at) AS periods,
    max(ingested_at) AS loaded_at
FROM {{ source('raw', 'raw_sidelined') }}
GROUP BY player_id
