# Tableau Calculated Fields

Create these calculated fields after connecting to
`SF_UDP_POC.MARTS.BI_NEIGHBORHOOD_DASHBOARD`.

## Avg Days To Close

```text
SUM([AVG_DAYS_TO_CLOSE] * [TOTAL_311_REQUESTS])
/
SUM(IF ISNULL([AVG_DAYS_TO_CLOSE]) THEN 0 ELSE [TOTAL_311_REQUESTS] END)
```

## Open Request Share

```text
SUM([OPEN_REQUEST_COUNT]) / SUM([TOTAL_311_REQUESTS])
```

## Construction To Complaint Ratio

```text
SUM([TOTAL_PERMITS]) / SUM([TOTAL_311_REQUESTS])
```

## Estimated Cost Per Request

```text
SUM([TOTAL_ESTIMATED_COST]) / SUM([TOTAL_311_REQUESTS])
```

## Estimated Cost Per Permit

```text
SUM([TOTAL_ESTIMATED_COST]) / SUM([TOTAL_PERMITS])
```

## City Avg Days To Close

```text
{ FIXED [MONTH_START_DATE] :
    SUM([AVG_DAYS_TO_CLOSE] * [TOTAL_311_REQUESTS])
    /
    SUM(IF ISNULL([AVG_DAYS_TO_CLOSE]) THEN 0 ELSE [TOTAL_311_REQUESTS] END)
}
```

## Response Index Vs City

```text
[Avg Days To Close] / [City Avg Days To Close]
```
