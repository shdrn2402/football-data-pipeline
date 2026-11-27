-- Staging must hold exactly the players of the latest details of every match.
-- A match whose latest details came without players is reported too.
SELECT fixture_id
FROM
(
    SELECT
        fixture_id,
        ingested_at,
        arraySum(
            team -> arrayCount(
                entry -> JSONExtractUInt(entry, 'player', 'id') != 0,
                JSONExtractArrayRaw(team, 'players')
            ),
            JSONExtractArrayRaw(payload, 'players')
        ) AS expected
    FROM {{ source('raw', 'raw_match_details') }} FINAL
) AS raw
FULL OUTER JOIN
(
    SELECT fixture_id, max(ingested_at) AS ingested_at, count() AS actual
    FROM {{ ref('stg_player_matches') }}
    GROUP BY fixture_id
) AS staging USING (fixture_id)
WHERE raw.expected != staging.actual
   OR (raw.expected > 0 AND raw.ingested_at != staging.ingested_at)
