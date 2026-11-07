ALTER TABLE mart_team_points DROP PARTITION ({league_id:UInt32}, {season:UInt16});

INSERT INTO mart_team_points
SELECT
    league_id,
    season,
    team_id,
    any(team_name) AS team_name,
    count() AS played,
    countIf(goals_for > goals_against) AS wins,
    countIf(goals_for = goals_against) AS draws,
    countIf(goals_for < goals_against) AS losses,
    sum(goals_for) AS goals_for_total,
    sum(goals_against) AS goals_against_total,
    3 * wins + draws AS points
FROM
(
    SELECT
        league_id,
        season,
        home_team_id AS team_id,
        home_team_name AS team_name,
        assumeNotNull(home_goals) AS goals_for,
        assumeNotNull(away_goals) AS goals_against
    FROM stg_fixtures FINAL
    WHERE league_id = {league_id:UInt32}
      AND season = {season:UInt16}
      AND status IN ('FT', 'AET', 'PEN')

    UNION ALL

    SELECT
        league_id,
        season,
        away_team_id AS team_id,
        away_team_name AS team_name,
        assumeNotNull(away_goals) AS goals_for,
        assumeNotNull(home_goals) AS goals_against
    FROM stg_fixtures FINAL
    WHERE league_id = {league_id:UInt32}
      AND season = {season:UInt16}
      AND status IN ('FT', 'AET', 'PEN')
)
GROUP BY league_id, season, team_id;
