-- One row per player and missed or doubtful match, from the latest snapshot of
-- each league season, so a row the API withdrew disappears.
{{ config(materialized='table', engine='MergeTree', order_by='(league_id, season, fixture_id, player_id)') }}

SELECT
    league_id,
    season,
    fixture_id,
    player_id,
    toUInt32(JSONExtractUInt(payload, 'team', 'id')) AS team_id,
    CAST(parseDateTimeBestEffort(JSONExtractString(payload, 'fixture', 'date'), 'UTC'), 'DateTime(\'UTC\')') AS match_at,
    toLowCardinality(JSONExtractString(payload, 'player', 'type')) AS type,
    JSONExtractString(payload, 'player', 'reason') AS reason,
    ingested_at
FROM {{ source('raw', 'raw_injuries') }} FINAL
WHERE (league_id, season, snapshot_date) IN
(
    SELECT league_id, season, max(snapshot_date)
    FROM {{ source('raw', 'raw_injuries') }}
    GROUP BY league_id, season
)
  AND player_id != 0
  AND fixture_id != 0
