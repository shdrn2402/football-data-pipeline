INSERT INTO stg_fixtures
SELECT
    league_id,
    season,
    fixture_id,
    parseDateTimeBestEffort(JSONExtractString(payload, 'fixture', 'date'), 'UTC'),
    JSONExtractString(payload, 'league', 'round'),
    JSONExtractString(payload, 'fixture', 'status', 'short'),
    JSONExtractUInt(payload, 'teams', 'home', 'id'),
    JSONExtractString(payload, 'teams', 'home', 'name'),
    JSONExtractUInt(payload, 'teams', 'away', 'id'),
    JSONExtractString(payload, 'teams', 'away', 'name'),
    JSONExtract(payload, 'goals', 'home', 'Nullable(UInt8)'),
    JSONExtract(payload, 'goals', 'away', 'Nullable(UInt8)'),
    ingested_at
FROM raw_fixtures FINAL
WHERE league_id = {league_id:UInt32}
  AND season = {season:UInt16}
  AND snapshot_date = {target_date:Date};
