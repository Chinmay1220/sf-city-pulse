select
    neighborhood,
    supervisor_district,
    date_trunc('month', permit_created_date)::date as month,
    count(*) as total_permits,
    sum(coalesce(estimated_cost, 0)) as total_estimated_cost,
    count_if(status in ('issued', 'approved', 'filed', 'reinstated')) as active_permit_count
from {{ ref('stg_building_permits') }}
group by 1, 2, 3
