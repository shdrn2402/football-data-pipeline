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

-- Latest details of every match. source_modified_at is the S3 modification time,
-- which tells whether the object changed since it was loaded.
CREATE TABLE IF NOT EXISTS raw_match_details
(
    league_id UInt32,
    season UInt16,
    fixture_id UInt64,
    ingested_at DateTime64(3, 'UTC'),
    source_modified_at DateTime('UTC'),
    payload String
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY (league_id, season)
ORDER BY (league_id, season, fixture_id);

-- One row per player of a players snapshot.
CREATE TABLE IF NOT EXISTS raw_players
(
    league_id UInt32,
    season UInt16,
    snapshot_date Date,
    player_id UInt64,
    ingested_at DateTime64(3, 'UTC'),
    payload String
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY (league_id, season)
ORDER BY (league_id, season, snapshot_date, player_id);

-- One row per requested player of a sidelined snapshot, '[]' without absences.
CREATE TABLE IF NOT EXISTS raw_sidelined
(
    league_id UInt32,
    season UInt16,
    snapshot_date Date,
    player_id UInt64,
    ingested_at DateTime64(3, 'UTC'),
    periods String
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY (league_id, season)
ORDER BY (league_id, season, snapshot_date, player_id);

-- One row per player and match of an injuries snapshot.
CREATE TABLE IF NOT EXISTS raw_injuries
(
    league_id UInt32,
    season UInt16,
    snapshot_date Date,
    fixture_id UInt64,
    player_id UInt64,
    ingested_at DateTime64(3, 'UTC'),
    payload String
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY (league_id, season)
ORDER BY (league_id, season, snapshot_date, fixture_id, player_id);

-- Staging tables are built and owned by dbt.

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
