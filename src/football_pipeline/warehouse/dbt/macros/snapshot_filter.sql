{# Selects the raw rows of the snapshot named by the run variables. #}
{# The variables are needed only to run: parsing must work without them, as other
   models are built with no variables. #}
{% macro snapshot_filter() -%}
{% if not execute %}1
{%- else -%}
league_id = {{ var('league_id') | int }}
  AND season = {{ var('season') | int }}
  AND snapshot_date = toDate('{{ modules.datetime.date.fromisoformat(var('snapshot_date') | string) }}')
{%- endif %}
{%- endmacro %}
