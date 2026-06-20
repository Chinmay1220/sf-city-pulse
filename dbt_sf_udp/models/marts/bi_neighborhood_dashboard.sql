{{ config(materialized='view') }}

with base as (
    select * from {{ ref('mart_neighborhood_equity') }}
),

city_monthly as (
    select
        month,
        sum(total_311_requests) as city_total_311_requests,
        sum(open_request_count) as city_open_request_count,
        sum(total_permits) as city_total_permits,
        sum(total_estimated_cost) as city_total_estimated_cost,
        sum(coalesce(avg_days_to_close, 0) * total_311_requests)
            / nullif(sum(iff(avg_days_to_close is not null, total_311_requests, 0)), 0)
            as city_avg_days_to_close
    from base
    group by 1
),

district_monthly as (
    select
        month,
        supervisor_district,
        sum(total_311_requests) as district_total_311_requests,
        sum(open_request_count) as district_open_request_count,
        sum(total_permits) as district_total_permits,
        sum(total_estimated_cost) as district_total_estimated_cost,
        sum(coalesce(avg_days_to_close, 0) * total_311_requests)
            / nullif(sum(iff(avg_days_to_close is not null, total_311_requests, 0)), 0)
            as district_avg_days_to_close
    from base
    group by 1, 2
)

select
    base.neighborhood,
    base.supervisor_district,
    case
        when base.supervisor_district between 1 and 11
            then 'District ' || base.supervisor_district::varchar
        else 'Unassigned'
    end as district_label,
    base.month as month_start_date,
    last_day(base.month) as month_end_date,
    to_char(base.month, 'YYYY-MM') as month_label,
    date_part('year', base.month) as year,
    date_part('quarter', base.month) as quarter,
    date_part('month', base.month) as month_number,
    date_part('year', base.month) * 100 + date_part('month', base.month) as month_sort_key,
    base.total_311_requests,
    base.avg_days_to_close,
    base.open_request_count,
    base.pct_open_requests,
    base.total_permits,
    base.total_estimated_cost,
    base.active_permit_count,
    base.construction_to_complaint_ratio,
    base.total_estimated_cost / nullif(base.total_311_requests, 0) as estimated_cost_per_request,
    base.total_estimated_cost / nullif(base.total_permits, 0) as estimated_cost_per_permit,
    base.active_permit_count / nullif(base.total_permits, 0) as active_permit_share,
    city_monthly.city_total_311_requests,
    city_monthly.city_open_request_count,
    city_monthly.city_open_request_count / nullif(city_monthly.city_total_311_requests, 0)
        as city_pct_open_requests,
    city_monthly.city_total_permits,
    city_monthly.city_total_estimated_cost,
    city_monthly.city_avg_days_to_close,
    district_monthly.district_total_311_requests,
    district_monthly.district_open_request_count,
    district_monthly.district_open_request_count / nullif(district_monthly.district_total_311_requests, 0)
        as district_pct_open_requests,
    district_monthly.district_total_permits,
    district_monthly.district_total_estimated_cost,
    district_monthly.district_avg_days_to_close,
    base.avg_days_to_close / nullif(city_monthly.city_avg_days_to_close, 0)
        as neighborhood_response_index_vs_city,
    district_monthly.district_avg_days_to_close / nullif(city_monthly.city_avg_days_to_close, 0)
        as district_response_index_vs_city,
    case
        when base.avg_days_to_close is null then 'No closed requests'
        when base.avg_days_to_close < 7 then 'Under 1 week'
        when base.avg_days_to_close < 14 then '1-2 weeks'
        when base.avg_days_to_close < 30 then '2-4 weeks'
        else '30+ days'
    end as response_time_bucket,
    case
        when base.total_311_requests >= 1000 then '1,000+ requests'
        when base.total_311_requests >= 500 then '500-999 requests'
        when base.total_311_requests >= 100 then '100-499 requests'
        else 'Under 100 requests'
    end as request_volume_bucket,
    case
        when base.total_permits = 0 then 'No permit activity'
        when base.total_permits < 10 then 'Light permit activity'
        when base.total_permits < 50 then 'Moderate permit activity'
        else 'High permit activity'
    end as construction_activity_bucket,
    case
        when base.avg_days_to_close > city_monthly.city_avg_days_to_close * 2
            then 'Above 2x city monthly average'
        when base.avg_days_to_close is null then 'No closed requests'
        else 'Within city range'
    end as neighborhood_equity_flag,
    case
        when district_monthly.district_avg_days_to_close > city_monthly.city_avg_days_to_close * 2
            then 'Above 2x city monthly average'
        when district_monthly.district_avg_days_to_close is null then 'No closed requests'
        else 'Within city range'
    end as district_equity_flag
from base
left join city_monthly
    on base.month = city_monthly.month
left join district_monthly
    on base.month = district_monthly.month
   and (
       base.supervisor_district = district_monthly.supervisor_district
       or (base.supervisor_district is null and district_monthly.supervisor_district is null)
   )
