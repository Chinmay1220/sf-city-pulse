# BI Dashboard Integration

Use this folder when you want a polished Power BI or Tableau version of the
Streamlit dashboard. Streamlit stays in the repo as the lightweight Python app;
the BI tools should connect to the dbt-powered Snowflake view below.

## Source View

Run dbt first:

```powershell
$env:DBT_PROFILES_DIR = "$PWD\dbt_sf_udp"
dbt build --project-dir dbt_sf_udp --select +bi_neighborhood_dashboard
```

Connect Power BI or Tableau to:

```text
SF_UDP_POC.MARTS.BI_NEIGHBORHOOD_DASHBOARD
```

This view keeps the monthly neighborhood grain from the original mart and adds
BI-friendly fields:

- `district_label`, `month_label`, `year`, `quarter`, and `month_sort_key`
- city and district monthly comparison fields
- response index fields for equity analysis
- request volume, response time, construction activity, and equity buckets
- cost-per-request, cost-per-permit, and active-permit share helpers

## Power BI Setup

1. Open Power BI Desktop.
2. Select `Get data` -> `Snowflake`.
3. Use the Snowflake server/account and warehouse `TRANSFORM_WH`.
4. Use database `SF_UDP_POC`, schema `MARTS`, and view
   `BI_NEIGHBORHOOD_DASHBOARD`.
5. Choose `Import` for a fast portfolio demo, or `DirectQuery` if you want the
   dashboard to query Snowflake live.
6. Load the view, then add the measures from `powerbi_measures.dax`.
7. Sort `month_label` by `month_sort_key`.

For a manual Power Query route, open `powerquery_sf_city_pulse.m`, replace
`YOUR_ACCOUNT.snowflakecomputing.com` with your Snowflake server, and paste the
query into Power BI's blank query advanced editor.

For a quick offline demo, generate a local CSV extract and open the generated
`.local.pbids` launcher. These generated files are ignored by Git because they
contain machine-specific paths and exported data.

Recommended pages:

- Executive Pulse: KPI cards, monthly 311 vs permit trend, top neighborhoods by
  request volume, and city average closure time.
- Equity by District: district slicer, response index bar chart, district trend
  against city average, and equity flag table.
- Construction vs Complaints: scatter plot with permits on X, 311 requests on
  Y, estimated cost as size, district as color, and neighborhood in tooltip.
- Neighborhood Drilldown: neighborhood slicer, monthly profile, KPI cards, and
  detailed table.

## Tableau Setup

1. Open Tableau Desktop.
2. Select `Connect` -> `To a Server` -> `Snowflake`.
3. Enter the Snowflake server/account, warehouse `TRANSFORM_WH`, database
   `SF_UDP_POC`, schema `MARTS`, and role `TRANSFORMER`.
4. Drag `BI_NEIGHBORHOOD_DASHBOARD` into the canvas.
5. Use an extract for a portfolio demo, or keep the connection live for a
   Snowflake-backed dashboard.
6. Add the calculated fields in `tableau_calculated_fields.md`.

Recommended sheets:

- City KPI strip
- Monthly activity dual-axis trend
- District response index bar chart
- Construction-versus-complaints scatter
- Neighborhood drilldown table

## Story Flow

The polished BI dashboard should tell the same story as the Streamlit app:

1. How much 311 and construction activity is happening citywide?
2. Which neighborhoods produce the most 311 volume?
3. Are any districts taking much longer than the city average?
4. Do construction-heavy neighborhoods also show higher complaint volume?
5. Which neighborhood deserves a closer operational review?
