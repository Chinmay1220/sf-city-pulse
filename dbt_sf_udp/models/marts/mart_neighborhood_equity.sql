with requests as (
    select * from {{ ref('int_311_by_neighborhood') }}
),

permits as (
    select * from {{ ref('int_permits_by_neighborhood') }}
),

joined as (
    select
        coalesce(requests.neighborhood, permits.neighborhood) as neighborhood,
        coalesce(requests.supervisor_district, permits.supervisor_district) as supervisor_district,
        coalesce(requests.month, permits.month) as month,
        coalesce(requests.total_requests, 0) as total_311_requests,
        requests.avg_days_to_close,
        coalesce(requests.open_request_count, 0) as open_request_count,
        coalesce(requests.pct_open, 0) as pct_open_requests,
        coalesce(permits.total_permits, 0) as total_permits,
        coalesce(permits.total_estimated_cost, 0) as total_estimated_cost,
        coalesce(permits.active_permit_count, 0) as active_permit_count
    from requests
    full outer join permits
        on requests.neighborhood = permits.neighborhood
       and requests.supervisor_district = permits.supervisor_district
       and requests.month = permits.month
)

select
    neighborhood,
    supervisor_district,
    month,
    total_311_requests,
    avg_days_to_close,
    open_request_count,
    pct_open_requests,
    total_permits,
    total_estimated_cost,
    active_permit_count,
    total_permits / nullif(total_311_requests, 0) as construction_to_complaint_ratio
from joined
