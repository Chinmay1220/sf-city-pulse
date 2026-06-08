with source as (
    select * from {{ source('raw', 'raw_311_requests') }}
),

renamed as (
    select
        service_request_id::varchar as service_request_id,
        try_to_timestamp_ntz(requested_datetime) as requested_at,
        try_to_timestamp_ntz(closed_date) as closed_at,
        case
            when lower(status_description::varchar) = 'open' then 'Open'
            when lower(status_description::varchar) = 'closed' then 'Closed'
            else initcap(status_description::varchar)
        end as status_description,
        service_name::varchar as service_name,
        try_to_number(supervisor_district) as supervisor_district,
        initcap(lower(nullif(trim(neighborhood::varchar), ''))) as neighborhood,
        try_to_double("LAT") as latitude,
        try_to_double("LONG") as longitude
    from source
)

select
    service_request_id,
    requested_at,
    closed_at,
    status_description,
    service_name,
    supervisor_district,
    neighborhood,
    latitude,
    longitude,
    case
        when closed_at >= requested_at then datediff('day', requested_at, closed_at)
    end as days_to_close,
    status_description = 'Open' as is_open
from renamed
where neighborhood is not null
  and requested_at is not null
qualify row_number() over (
    partition by service_request_id
    order by requested_at desc
) = 1
