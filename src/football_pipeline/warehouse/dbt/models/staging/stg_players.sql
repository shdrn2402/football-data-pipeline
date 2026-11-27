-- One row per player: the profile of the latest load.
{{ config(materialized='table', engine='MergeTree', order_by='player_id') }}

SELECT
    player_id,
    JSONExtractString(latest, 'player', 'name') AS player_name,
    JSONExtractString(latest, 'player', 'firstname') AS first_name,
    JSONExtractString(latest, 'player', 'lastname') AS last_name,
    toDate32OrNull(JSONExtractString(latest, 'player', 'birth', 'date')) AS birth_date,
    nullIf(JSONExtractString(latest, 'player', 'nationality'), '') AS nationality,
    loaded_at AS ingested_at
FROM
(
    SELECT
        player_id,
        argMax(payload, ingested_at) AS latest,
        max(ingested_at) AS loaded_at
    FROM {{ source('raw', 'raw_players') }}
    WHERE player_id != 0
    GROUP BY player_id
)
