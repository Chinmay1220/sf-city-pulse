select 1
where not exists (
    select 1
    from {{ ref('mart_neighborhood_equity') }}
)
