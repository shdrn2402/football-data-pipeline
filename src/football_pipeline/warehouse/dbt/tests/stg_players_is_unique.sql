SELECT player_id
FROM {{ ref('stg_players') }}
GROUP BY player_id
HAVING count() > 1
