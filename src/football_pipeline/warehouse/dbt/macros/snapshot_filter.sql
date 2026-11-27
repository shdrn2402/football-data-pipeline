{# Selects the raw rows of the snapshot named by the run variables. #}
{% macro snapshot_filter() -%}
league_id = {{ var('league_id') | int }}
  AND season = {{ var('season') | int }}
  AND snapshot_date = toDate('{{ modules.datetime.date.fromisoformat(var('snapshot_date') | string) }}')
{%- endmacro %}
