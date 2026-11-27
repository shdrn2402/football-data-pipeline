-- Every fixture of the snapshot must have reached staging.
SELECT fixture_id
FROM {{ source('raw', 'raw_fixtures') }} FINAL
WHERE {{ snapshot_filter() }}
  AND fixture_id NOT IN (
      SELECT fixture_id
      FROM {{ ref('stg_fixtures') }}
      WHERE league_id = {{ var('league_id') | int }}
        AND season = {{ var('season') | int }}
  )
