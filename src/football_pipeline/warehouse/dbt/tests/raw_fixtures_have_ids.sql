-- JSONExtractUInt returns 0 for a missing field, so a changed response format
-- would otherwise load silently. A test on a source runs before the models that
-- read it, and a failure skips them, which keeps broken rows out of staging.
SELECT fixture_id
FROM {{ source('raw', 'raw_fixtures') }} FINAL
WHERE {{ snapshot_filter() }}
  AND (
      fixture_id = 0
      OR JSONExtractUInt(payload, 'teams', 'home', 'id') = 0
      OR JSONExtractUInt(payload, 'teams', 'away', 'id') = 0
  )
