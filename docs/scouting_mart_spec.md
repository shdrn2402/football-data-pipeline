# Football Scouting Mart Specification

## 1. Goal

Automated first-pass screening of footballers in European stepping-stone leagues: EFL Championship, Eredivisie, Liga Portugal and Belgian Pro League.

The platform solves two tasks in two stages:

| Stage | Task | Data |
|---|---|---|
| v1 | Find talented players by on-pitch efficiency, discipline and availability | API-Football |
| v2 | Find undervalued players and backtest whether high efficiency leads to market value growth | API-Football and market values from transfermarkt-datasets |

Player statistics are the core. Match results are secondary context. Screening and backtesting use finished seasons. The ongoing season is loaded during the paid plan month to demonstrate work with live data.

## 2. Layers

| Layer | Grain | Content |
|---|---|---|
| Staging | player and match | All match statistics with club and league (`stg_player_matches`). Profiles, absence periods and injuries are separate staging tables |
| `dm_scouting_efficiency` | `(player_id, season)` | One row per player and season for screening |

Staging and the mart are dbt models on ClickHouse; loading raw data from S3 is done in Python.

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
| `injury_matches_missed` | `Nullable(UInt16)` | Club matches dated within an injury or illness period of `/sidelined` |
| `suspension_matches_missed` | `Nullable(UInt16)` | `/injuries` rows of type `Missing Fixture` with reason `Red Card`, `Yellow Cards` or `Suspended`. `NULL` for league seasons without `/injuries` data |
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
- **One source for all leagues:** availability comes from `/sidelined`, so leagues are comparable. `/injuries` has no data for some leagues and is used only to cross-check where it exists.
- **Suspensions are never estimated:** `/sidelined` misses most of them and card rules differ between leagues, so a league season without `/injuries` keeps `NULL`. Cards from match statistics still cover discipline in every league.
- **Missing statistics:** for a player with minutes in a match with statistics, a `null` counting statistic means `0`. For unused substitutes, and for matches where no player has a pass count, it stays `NULL`. `rating` is never filled in.
- **Never asked or never absent:** a player in the requested list of a `/sidelined` snapshot without periods has no known absence. A player not in the list has `NULL`.
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
| Injuries per match | `/injuries` with `league` and `season` | No injury dates. Reasons include cards, suspensions and national team duty. Cross-check only |
| Absence periods | `/sidelined` with `players`, at most 20 per request | Includes suspensions. Players without periods are omitted |
| Age and nationality | `/players` with `league` and `season`, 20 players per page | The free plan returns at most 3 pages. Age is computed from the date of birth, as the `age` field is the current one |
| Market value | [transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets): `player_valuations` and `players` | v2, see below |

Observed on the free plan on 2026-11-27: Eredivisie 2023 `/injuries` returned 1769 rows for 297 players in one request. `/sidelined` accepted five players in one request. Match events have no ID of their own, so the details of a match must be replaced as a whole.

### Source quality findings

Checked on 2026-11-27 on the free plan, mostly on small samples.

| Finding | Evidence |
|---|---|
| No `/injuries` data for Liga Portugal and the Belgian Pro League | 0 rows for 2023 and 2024, while EFL Championship returned 3698 and Eredivisie 1769 for 2023. The league coverage flag is off for 2021 to 2024 and 2026, and on for 2025 |
| `/sidelined` agrees well with `/injuries` | For 20 often injured Eredivisie players, its periods cover 161 of 171 injury absences. One player had none of 6 covered |
| `/sidelined` misses most suspensions | Of the suspension absences in `/injuries` 2023, its suspension periods cover 20 of 113 (18%) in Eredivisie and 12 of 110 (11%) in EFL Championship. Matches inside those periods are mostly confirmed: 20 of 21 and 12 of 18 |
| `/sidelined` is still updated, unevenly across samples | For the 55 players of Ajax 2023 the newest period starts on 2026-10-28. In earlier samples of about 80 players nothing started after September 2025 |
| Date of birth and nationality are filled | 80 of 80 players, 20 per league |
| `passes.accuracy` is a number of accurate passes, not a percentage | Never above `passes.total` in 147 player matches |
| `null` in counting statistics of a player who played means zero | Goals, assists, shots, key passes, tackles and dribbles hold no zeros, only `null`. Cards do use `0`. Checked on 4 Premier League matches |
| `end: null` in `/sidelined` | 14 periods starting in 2024 and 2025, none followed by a newer period in these samples |
| `/players` pages in 2023 | 59, 49, 43 and 37 for Championship, Eredivisie, Liga Portugal and Belgium |
| Counting statistics follow the same rule in the Eredivisie | No zeros among players who played, only `null`, in 5 Ajax matches |
| Player goals agree with the score | 20 of 20 team matches in 5 Premier League and 5 Eredivisie matches |
| `/players` covers match details | All 35 Ajax players of 5 matches are in the Ajax 2023 snapshot |
| `passes.accuracy` can be missing | 3 player matches have passes but no accuracy, kept as `NULL` |
| `/sidelined` types are free text | Most frequent for Ajax 2023: `Knock`, `Knee Injury`, `Unknown`, `Hamstring`, `Illness` |

### Market value source

Checked on 2026-11-27 on files dated 2026-09-05. `player_valuations` holds 656301 rows (player, date, value in EUR, club) from 2000-01-20 to 2026-06-12, with no duplicate player and date. `players` holds date of birth, citizenship and position. `clubs` is not needed.

| Finding | Rule or consequence |
|---|---|
| EFL Championship has no competition code and no clubs in `clubs`. Valuations of its clubs carry other codes or none | Join by player and take the league from API-Football. Measure the coverage of Championship players |
| Fewer players are valued in recent years: 27890 in 2023, 19628 in 2024, 18951 in 2025 | Some players have no next season value, possibly not at random. Report the share in the backtest |
| Valuations cluster in June and December | Cut off at the end of June and limit the age of a valuation |
| `players` holds current and highest values | Never use them as features. Take values only from `player_valuations` |
| Date of birth is filled for 5002 of 5004 players seen in the Dutch, Portuguese and Belgian competition codes since July 2022. Only 2 rows of the file share name and date of birth | Match players by full name and date of birth from API-Football profiles, since match details give short names |
| The dataset repository declares CC0, the data comes from Transfermarkt, whose terms were not checked. The download link was not confirmed from the maintainer | Check both before use. Do not commit the files |

## 7. Open questions

To verify on data before the related fields are implemented:

- Does `null` mean zero in all four tracked leagues, and what if only some statistics of a match are covered?
- Are date of birth and absence periods filled for all players, not only in samples?
- How complete and how fresh is `/sidelined` for the ongoing season in each league?
- How should `end: null` in `/sidelined` be treated? It also occurs in old records followed by newer ones.
- Which `/sidelined` types count as injury or illness, for example `Unknown`?
- Does `/players` list everyone who appears in match details, for whole leagues?
- Do `/injuries` suspension rows agree with the cards in match statistics?
- Does the paid plan give access to the ongoing season?
- After the paid load, what is the coverage of `/injuries` and `/sidelined`, including suspensions, for all tracked leagues and seasons?

To decide:

- How many days of finished matches an ongoing season downloads again
- Position weights of the efficiency index
- `availability_rate` for a player with several clubs
- Terms of use of the market value data and the maximum age of a valuation
- Seasons to load
