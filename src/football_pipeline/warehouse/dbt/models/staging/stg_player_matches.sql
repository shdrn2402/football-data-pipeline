-- One row per player and match, with the club and league of that match.
-- A reloaded match replaces all of its rows, so a player removed by a correction
-- does not stay behind. full_refresh is safe here: raw holds every loaded match.
{{
    config(
        incremental_strategy='delete_insert',
        unique_key='fixture_id',
        engine='MergeTree',
        order_by='(league_id, season, fixture_id, player_id)',
        partition_by='(league_id, season)'
    )
}}

WITH matches AS
(
    SELECT league_id, season, fixture_id, ingested_at, payload
    FROM {{ source('raw', 'raw_match_details') }} FINAL
    {% if is_incremental() %}
    WHERE (fixture_id, ingested_at) NOT IN (SELECT fixture_id, ingested_at FROM {{ this }})
    {% endif %}
),

teams AS
(
    SELECT *, arrayJoin(JSONExtractArrayRaw(payload, 'players')) AS team
    FROM matches
),

entries AS
(
    SELECT *, arrayJoin(JSONExtractArrayRaw(team, 'players')) AS entry
    FROM teams
),

players AS
(
    SELECT
        *,
        JSONExtractRaw(entry, 'statistics', 1) AS statistics,
        toUInt16(JSONExtractUInt(statistics, 'games', 'minutes')) AS minutes_played,
        -- A match without any pass count has no player statistics at all.
        max(JSONExtract(statistics, 'passes', 'total', 'Nullable(UInt16)') IS NOT NULL)
            OVER (PARTITION BY fixture_id) AS has_statistics
    FROM entries
)

SELECT
    league_id,
    season,
    fixture_id,
    JSONExtractUInt(entry, 'player', 'id') AS player_id,
    JSONExtractString(entry, 'player', 'name') AS player_name,
    toUInt32(JSONExtractUInt(team, 'team', 'id')) AS team_id,
    JSONExtractString(team, 'team', 'name') AS team_name,
    CAST(parseDateTimeBestEffort(JSONExtractString(payload, 'fixture', 'date'), 'UTC'), 'DateTime(\'UTC\')') AS match_at,
    toLowCardinality(JSONExtractString(payload, 'fixture', 'status', 'short')) AS status,
    team_id = JSONExtractUInt(payload, 'teams', 'home', 'id') AS is_home,
    JSONExtract(payload, 'goals', if(is_home, 'home', 'away'), 'Nullable(UInt8)') AS team_goals,
    JSONExtract(payload, 'goals', if(is_home, 'away', 'home'), 'Nullable(UInt8)') AS opponent_goals,
    toLowCardinality(JSONExtractString(statistics, 'games', 'position')) AS position,
    minutes_played,
    minutes_played > 0 AND NOT JSONExtractBool(statistics, 'games', 'substitute') AS is_starter,
    JSONExtractBool(statistics, 'games', 'captain') AS is_captain,
    -- Sent as a string.
    toDecimal32OrNull(JSONExtractString(statistics, 'games', 'rating'), 2) AS rating,
    {{ played_count("'goals', 'total'") }} AS goals,
    {{ played_count("'goals', 'assists'") }} AS assists,
    {{ played_count("'goals', 'conceded'") }} AS goals_conceded,
    {{ played_count("'goals', 'saves'") }} AS saves,
    {{ played_count("'offsides'") }} AS offsides,
    {{ played_count("'shots', 'total'") }} AS shots_total,
    {{ played_count("'shots', 'on'") }} AS shots_on,
    {{ played_count("'passes', 'total'") }} AS passes_total,
    {{ played_count("'passes', 'key'") }} AS passes_key,
    {{ played_count("'tackles', 'total'") }} AS tackles,
    {{ played_count("'tackles', 'blocks'") }} AS blocks,
    {{ played_count("'tackles', 'interceptions'") }} AS interceptions,
    {{ played_count("'duels', 'total'") }} AS duels_total,
    {{ played_count("'duels', 'won'") }} AS duels_won,
    {{ played_count("'dribbles', 'attempts'") }} AS dribbles_attempts,
    {{ played_count("'dribbles', 'success'") }} AS dribbles_success,
    {{ played_count("'dribbles', 'past'") }} AS dribbles_past,
    {{ played_count("'fouls', 'drawn'") }} AS fouls_drawn,
    {{ played_count("'fouls', 'committed'") }} AS fouls_committed,
    {{ played_count("'cards', 'yellow'") }} AS yellow_cards,
    {{ played_count("'cards', 'red'") }} AS red_cards,
    {{ played_count("'penalty', 'won'") }} AS penalties_won,
    {{ played_count("'penalty', 'commited'") }} AS penalties_conceded,
    {{ played_count("'penalty', 'scored'") }} AS penalties_scored,
    {{ played_count("'penalty', 'missed'") }} AS penalties_missed,
    {{ played_count("'penalty', 'saved'") }} AS penalties_saved,
    -- "accuracy" is the number of accurate passes, sent as a string.
    multiIf(
        passes_total IS NULL, NULL,
        passes_total = 0, toUInt16(0),
        toUInt16OrNull(JSONExtractString(statistics, 'passes', 'accuracy'))
    ) AS passes_accurate,
    ingested_at
FROM players
WHERE player_id != 0
