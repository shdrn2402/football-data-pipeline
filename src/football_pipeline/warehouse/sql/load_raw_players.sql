INSERT INTO raw_players (league_id, season, snapshot_date, player_id, ingested_at, payload)
SELECT
    {league_id:UInt32},
    {season:UInt16},
    {snapshot_date:Date},
    JSONExtractUInt(item, 'player', 'id'),
    parseDateTime64BestEffort(JSONExtractString(json, '_metadata', 'ingested_at'), 3, 'UTC'),
    item
FROM s3({s3_url:String}, '__AWS_ACCESS_KEY_ID__', '__AWS_SECRET_ACCESS_KEY__', 'JSONAsString', 'json String')
ARRAY JOIN JSONExtractArrayRaw(json, 'payload', 'response') AS item;
