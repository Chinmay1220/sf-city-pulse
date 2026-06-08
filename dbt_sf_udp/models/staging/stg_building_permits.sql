with source as (
    select * from {{ source('raw', 'raw_building_permits') }}
),

renamed as (
    select
        permit_number::varchar as permit_number,
        permit_type::varchar as permit_type,
        try_to_date(permit_creation_date) as permit_created_date,
        lower(trim(status::varchar)) as status,
        initcap(lower(nullif(trim(neighborhoods_analysis_boundaries::varchar), ''))) as neighborhood,
        try_to_number(supervisor_district) as supervisor_district,
        try_to_decimal(
            nullif(regexp_replace(estimated_cost::varchar, '[^0-9.-]', ''), ''),
            18,
            2
        ) as estimated_cost,
        street_name::varchar as street_name
    from source
)

select
    permit_number,
    permit_type,
    permit_created_date,
    status,
    neighborhood,
    supervisor_district,
    estimated_cost,
    street_name
from renamed
where neighborhood is not null
  and permit_created_date is not null
  and status in ('issued', 'approved', 'filed', 'reinstated')
qualify row_number() over (
    partition by permit_number
    order by permit_created_date desc
) = 1
