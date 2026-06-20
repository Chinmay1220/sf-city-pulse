let
    Source = Snowflake.Databases(
        "YOUR_ACCOUNT.snowflakecomputing.com",
        "TRANSFORM_WH",
        [Database = "SF_UDP_POC", Role = "TRANSFORMER", Implementation = "2.0"]
    ),
    SF_UDP_POC_Database = Source{[Name = "SF_UDP_POC", Kind = "Database"]}[Data],
    MARTS_Schema = SF_UDP_POC_Database{[Name = "MARTS", Kind = "Schema"]}[Data],
    BI_NEIGHBORHOOD_DASHBOARD_View =
        MARTS_Schema{[Name = "BI_NEIGHBORHOOD_DASHBOARD", Kind = "View"]}[Data]
in
    BI_NEIGHBORHOOD_DASHBOARD_View
