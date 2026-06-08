{% test assert_average_gt(model, column_name, min_value=0) %}
with validation as (
    select avg({{ column_name }}) as average_value
    from {{ model }}
    where {{ column_name }} is not null
)

select *
from validation
where average_value is null
   or average_value <= {{ min_value }}
{% endtest %}
