-- The API omits players without absences, so rows come from the requested IDs.
INSERT INTO raw_sidelined (league_id, season, snapshot_date, player_id, ingested_at, periods)
SELECT
    {league_id:UInt32},
    {season:UInt16},
    {snapshot_date:Date},
    requested_id,
    parseDateTime64BestEffort(JSONExtractString(json, '_metadata', 'ingested_at'), 3, 'UTC'),
    coalesce(
        nullIf(
            JSONExtractRaw(
                arrayFirst(
                    item -> JSONExtractUInt(item, 'id') = requested_id,
                    JSONExtractArrayRaw(json, 'payload', 'response')
                ),
                'sidelined'
            ),
            ''
        ),
        '[]'
    )
FROM s3({s3_url:String}, '__AWS_ACCESS_KEY_ID__', '__AWS_SECRET_ACCESS_KEY__', 'JSONAsString', 'json String')
ARRAY JOIN JSONExtract(json, '_metadata', 'params', 'players', 'Array(UInt64)') AS requested_id;
