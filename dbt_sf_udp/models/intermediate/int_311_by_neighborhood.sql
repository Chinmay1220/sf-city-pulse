select
    neighborhood,
    supervisor_district,
    date_trunc('month', requested_at)::date as month,
    count(*) as total_requests,
    avg(days_to_close) as avg_days_to_close,
    count_if(is_open) as open_request_count,
    count_if(is_open) / nullif(count(*), 0) as pct_open
from {{ ref('stg_311_requests') }}
group by 1, 2, 3
