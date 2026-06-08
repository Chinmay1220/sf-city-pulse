{% test assert_column_gte(model, column_name, min_value=0) %}
select *
from {{ model }}
where {{ column_name }} is not null
  and {{ column_name }} < {{ min_value }}
{% endtest %}
