-- One row per fixture: the version with the latest ingested_at wins.
-- Each run appends one snapshot of one league season.
-- full_refresh is off: rebuilding from a single snapshot would drop every other season.
{{
    config(
        incremental_strategy='append',
        engine='ReplacingMergeTree(ingested_at)',
        order_by='(league_id, season, fixture_id)',
        partition_by='(league_id, season)',
        full_refresh=false
    )
}}

SELECT
    league_id,
    season,
    fixture_id,
    CAST(parseDateTimeBestEffort(JSONExtractString(payload, 'fixture', 'date'), 'UTC'), 'DateTime(\'UTC\')') AS match_at,
    JSONExtractString(payload, 'league', 'round') AS round,
    toLowCardinality(JSONExtractString(payload, 'fixture', 'status', 'short')) AS status,
    toUInt32(JSONExtractUInt(payload, 'teams', 'home', 'id')) AS home_team_id,
    JSONExtractString(payload, 'teams', 'home', 'name') AS home_team_name,
    toUInt32(JSONExtractUInt(payload, 'teams', 'away', 'id')) AS away_team_id,
    JSONExtractString(payload, 'teams', 'away', 'name') AS away_team_name,
    JSONExtract(payload, 'goals', 'home', 'Nullable(UInt8)') AS home_goals,
    JSONExtract(payload, 'goals', 'away', 'Nullable(UInt8)') AS away_goals,
    ingested_at
FROM {{ source('raw', 'raw_fixtures') }} FINAL
WHERE {{ snapshot_filter() }}
