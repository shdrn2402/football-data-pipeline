INSERT INTO raw_match_details (league_id, season, fixture_id, ingested_at, source_modified_at, payload)
SELECT
    JSONExtractUInt(item, 'league', 'id'),
    JSONExtractUInt(item, 'league', 'season'),
    JSONExtractUInt(item, 'fixture', 'id'),
    parseDateTime64BestEffort(JSONExtractString(json, '_metadata', 'ingested_at'), 3, 'UTC'),
    assumeNotNull(_time),
    item
FROM s3({s3_url:String}, '__AWS_ACCESS_KEY_ID__', '__AWS_SECRET_ACCESS_KEY__', 'JSONAsString', 'json String')
ARRAY JOIN JSONExtractArrayRaw(json, 'payload', 'response') AS item;
