-- One row per fixture per snapshot, keeping the original API JSON untouched.
CREATE TABLE IF NOT EXISTS raw_fixtures
(
    league_id UInt32,
    season UInt16,
    snapshot_date Date,
    fixture_id UInt64,
    ingested_at DateTime64(3, 'UTC'),
    payload String
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY (league_id, season)
ORDER BY (league_id, season, snapshot_date, fixture_id);

-- One row per fixture: the version with the latest ingested_at wins.
CREATE TABLE IF NOT EXISTS stg_fixtures
(
    league_id UInt32,
    season UInt16,
    fixture_id UInt64,
    match_at DateTime('UTC'),
    round String,
    status LowCardinality(String),
    home_team_id UInt32,
    home_team_name String,
    away_team_id UInt32,
    away_team_name String,
    home_goals Nullable(UInt8),
    away_goals Nullable(UInt8),
    ingested_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY (league_id, season)
ORDER BY (league_id, season, fixture_id);

-- Fully rebuilt per league and season, so a plain MergeTree is enough.
CREATE TABLE IF NOT EXISTS mart_team_points
(
    league_id UInt32,
    season UInt16,
    team_id UInt32,
    team_name String,
    played UInt16,
    wins UInt16,
    draws UInt16,
    losses UInt16,
    goals_for UInt16,
    goals_against UInt16,
    points UInt16
)
ENGINE = MergeTree
PARTITION BY (league_id, season)
ORDER BY (league_id, season, team_id);
