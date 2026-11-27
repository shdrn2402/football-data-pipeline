-- A changed response format would load zeros silently. This runs before the model.
SELECT fixture_id
FROM {{ source('raw', 'raw_match_details') }} FINAL
WHERE fixture_id = 0
   OR league_id = 0
   OR arrayExists(
       team -> JSONExtractUInt(team, 'team', 'id') = 0,
       JSONExtractArrayRaw(payload, 'players')
   )
