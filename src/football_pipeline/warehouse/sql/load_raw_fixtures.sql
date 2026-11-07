INSERT INTO raw_fixtures (league_id, season, snapshot_date, fixture_id, ingested_at, payload)
SELECT
    {league_id:UInt32},
    {season:UInt16},
    {target_date:Date},
    JSONExtractUInt(fixture, 'fixture', 'id'),
    parseDateTime64BestEffort(JSONExtractString(json, '_metadata', 'ingested_at'), 3, 'UTC'),
    fixture
FROM s3({s3_url:String}, '__AWS_ACCESS_KEY_ID__', '__AWS_SECRET_ACCESS_KEY__', 'JSONAsString', 'json String')
ARRAY JOIN JSONExtractArrayRaw(json, 'payload', 'response') AS fixture;
