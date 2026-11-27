# Football Scouting Mart Specification

## 1. Goal

Automated first-pass screening of footballers in European stepping-stone leagues: EFL Championship, Eredivisie, Liga Portugal and Belgian Pro League.

The platform solves two tasks in two stages:

| Stage | Task | Data |
|---|---|---|
| v1 | Find talented players by on-pitch efficiency, discipline and availability | API-Football |
| v2 | Find undervalued players and backtest whether high efficiency leads to market value growth | API-Football and an external market value source (to be chosen) |

Player statistics are the core. Match results are secondary context. Screening and backtesting use finished seasons. The ongoing season is loaded during the paid plan month to demonstrate work with live data.

## 2. Layers

| Layer | Grain | Content |
|---|---|---|
| Staging | player and match | All match statistics with club and league |
| `dm_scouting_efficiency` | `(player_id, season)` | One row per player and season for screening |

The mart is the only Gold table. Any split by club or league is built from staging.

A season is identified by its start year. The mart is rebuilt per season across all tracked leagues.

## 3. Mart fields

`Nullable` means "no data". It must never be read as zero.

### Identity and profile

| Field | Type | Description |
|---|---|---|
| `player_id` | `UInt64` | API-Football player ID (key) |
| `season` | `UInt16` | Season start year (key) |
| `player_name` | `String` | Normalized player name |
| `age_at_season_start` | `Nullable(UInt8)` | Age on the first day of the season of the primary league |
| `nationality` | `LowCardinality(Nullable(String))` | Nationality |
| `primary_position` | `LowCardinality(String)` | Position with the most minutes in the season |
| `primary_league_id` | `UInt32` | Tracked league with the most minutes |
| `current_club_id` | `UInt64` | Club of the player's last match in the season |
| `clubs_count` | `UInt8` | Clubs the player appeared for in the tracked leagues |
| `is_season_complete` | `UInt8` | `0` for an ongoing season, whose percentiles are not comparable with finished ones |

### Playing time

| Field | Type | Description |
|---|---|---|
| `matches_played` | `UInt16` | Matches with at least one minute |
| `matches_started` | `UInt16` | Matches in the starting eleven |
| `total_minutes_played` | `UInt32` | Minutes on the pitch |
| `is_eligible` | `UInt8` | `1` if minutes reach the threshold |
| `is_impact_sub` | `UInt8` | `1` if below the threshold with at least 3 goal involvements |

### Attack

| Field | Type |
|---|---|
| `goals`, `assists` | `UInt16` |
| `goals_per_90`, `assists_per_90`, `goal_involvement_per_90` | `Decimal(5,2)` |
| `shots_on_per_90`, `key_passes_per_90`, `dribbles_success_per_90` | `Nullable(Decimal(5,2))` |

### Defence and efficiency

| Field | Type | Description |
|---|---|---|
| `tackles_per_90`, `interceptions_per_90`, `blocks_per_90`, `duels_won_per_90` | `Nullable(Decimal(5,2))` | |
| `duels_won_pct`, `dribbles_success_pct`, `pass_accuracy_pct` | `Nullable(Decimal(5,2))` | `0` to `100` |
| `avg_rating` | `Nullable(Decimal(4,2))` | API rating weighted by minutes |
| `saves_per_90`, `goals_conceded_per_90` | `Nullable(Decimal(5,2))` | Goalkeepers only |

### Discipline

| Field | Type | Description |
|---|---|---|
| `yellow_cards`, `red_cards` | `UInt16` | |
| `cards_per_90` | `Decimal(5,2)` | Yellow and red cards |
| `fouls_committed_per_90`, `fouls_drawn_per_90` | `Nullable(Decimal(5,2))` | |
| `penalties_conceded` | `Nullable(UInt8)` | API field `penalty.commited` (spelled this way) |

### Availability

| Field | Type | Description |
|---|---|---|
| `injury_days_lost` | `Nullable(UInt16)` | Days out through injury or illness within the season (`/sidelined`) |
| `injury_matches_missed` | `Nullable(UInt16)` | `/injuries` rows of type `Missing Fixture` with an injury or illness reason |
| `suspension_matches_missed` | `Nullable(UInt16)` | `/injuries` rows of type `Missing Fixture` with reason `Red Card`, `Yellow Cards` or `Suspended` |
| `availability_rate` | `Nullable(Decimal(4,3))` | `1 - injury_matches_missed / club matches`, from `0.000` to `1.000` |

### Context and score

| Field | Type | Description |
|---|---|---|
| `team_points_per_match` | `Nullable(Decimal(4,2))` | Results of the player's clubs, weighted by the player's minutes |
| `position_percentile` | `Nullable(Decimal(5,2))` | Rank among players of the same league, season and position |
| `age_group_percentile` | `Nullable(Decimal(5,2))` | Same, limited to the player's age group |
| `efficiency_index` | `Nullable(Decimal(8,3))` | Composite score |

### Market value (v2)

| Field | Type | Description |
|---|---|---|
| `market_value_eur` | `Nullable(Decimal(12,2))` | Value on the season cut-off date (`ASOF JOIN`) |
| `next_season_market_value_eur` | `Nullable(Decimal(12,2))` | Value one season later |
| `value_delta_eur` | `Nullable(Decimal(12,2))` | `next_season_market_value_eur - market_value_eur` |
| `price_growth_pct` | `Nullable(Decimal(10,2))` | Relative growth in percent |

## 4. Rules

- **Minutes threshold:** 450, set in configuration. Players below it stay in the mart but get no percentiles and no index.
- **Age groups** (by `age_at_season_start`): under 21, 21 to 23, 24 and older.
- **Impact substitutes:** `is_impact_sub` marks players below the threshold with at least 3 goals and assists combined.
- **Availability:** only injuries and illness lower `availability_rate`. Suspensions are counted separately, and unused matches on the bench do not count.
- **Several clubs or leagues:** statistics are summed. Percentiles use the primary league.
- **Efficiency index:** weighted percentiles with weights per position, a discipline penalty, multiplied by availability. Weights are fixed before any backtest.
- **No data leakage:** features use only what was known on the season cut-off date. `next_season_market_value_eur`, `value_delta_eur` and `price_growth_pct` are targets and never feed the index.
- **Injury periods:** clipped to the season dates, so a period crossing two seasons is not counted twice. The summer break is not counted.
- **`Questionable` rows** in `/injuries` are not missed matches.

## 5. Loading rules

One algorithm and one DAG serve finished and ongoing seasons:

1. Get the fixture list of a league season.
2. Select finished matches by the status of each match.
3. Download details only for matches that are not stored yet.
4. Load ClickHouse and rebuild the mart.

An ongoing season also needs:

| Case | Behaviour |
|---|---|
| Postponed, abandoned or cancelled match | Not finished, no details. A later run sees the new date or status |
| Late or corrected match details | Matches of the last days are downloaded again |
| New injuries and absence periods | Refreshed regularly, not only when missing |
| Daily run | Scheduled |

A daily snapshot of the fixture list stays in S3, so changes can be replayed after the paid plan ends. Tests cover a postponed match that is played later, a moved date and corrected statistics. An as-of date shows incremental loading on a finished season, but it cannot show rescheduling: the API returns the final state.

## 6. Data sources

| Data | Endpoint | Notes |
|---|---|---|
| Match statistics, events, lineups | `/fixtures` with `id` (free plan) or `ids` (paid plan, up to 20 matches) | `ids` is rejected on the free plan |
| Injuries per match | `/injuries` with `league` and `season` | No injury dates. Reasons include cards, suspensions and national team duty |
| Absence periods | `/sidelined` with `player` or `players` | Not yet in `configs/config.yaml` |
| Age and nationality | Player profile endpoint | To be chosen and verified |
| Market value | External source | v2 |

Observed on the free plan on 2026-11-27: Eredivisie 2023 `/injuries` returned 1769 rows for 297 players in one request. `/sidelined` accepted five players in one request. Match events have no ID of their own, so the details of a match must be replaced as a whole.

## 7. Open questions

To verify on data before the related fields are implemented:

- Is `passes.accuracy` a percentage or a number of accurate passes? One sample suggests a number.
- Does `null` in player statistics mean zero or missing data?
- Are age, injuries and absence periods covered for all four leagues?
- How should `end: null` in `/sidelined` be treated? It also occurs in old records followed by newer ones.
- Does `/sidelined` include suspensions, and how many players does one request accept?
- Do `/injuries` suspension rows agree with the cards in match statistics?
- Does the paid plan give access to the ongoing season?

To decide:

- How many days of finished matches an ongoing season downloads again
- Position weights of the efficiency index
- `availability_rate` for a player with several clubs
- Market value source, its terms of use and the way players are matched to it
- Seasons to load
