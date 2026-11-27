SELECT fixture_id, player_id
FROM {{ ref('stg_injuries') }}
GROUP BY fixture_id, player_id
HAVING count() > 1
