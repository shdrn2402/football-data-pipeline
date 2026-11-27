-- Such players cannot be tracked and are left out of staging.
{{ config(severity='warn') }}

SELECT fixture_id
FROM {{ source('raw', 'raw_match_details') }} FINAL
WHERE arrayExists(
    team -> arrayExists(
        entry -> JSONExtractUInt(entry, 'player', 'id') = 0,
        JSONExtractArrayRaw(team, 'players')
    ),
    JSONExtractArrayRaw(payload, 'players')
)
