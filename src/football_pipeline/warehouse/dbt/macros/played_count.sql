{# A counting statistic of one player match. The API sends null instead of 0 for a
   player who played. Without minutes, or in a match without statistics, it stays NULL. #}
{% macro played_count(path, type='UInt16') -%}
if(
    minutes_played > 0 AND has_statistics,
    to{{ type }}(coalesce(JSONExtract(statistics, {{ path }}, 'Nullable({{ type }})'), 0)),
    NULL
)
{%- endmacro %}
