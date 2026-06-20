import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const biDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.join(biDir, "SFCityPulse.PowerBI.local");
const reportDir = path.join(projectRoot, "SF City Pulse.Report");
const reportDefinitionDir = path.join(reportDir, "definition");
const pagesDir = path.join(reportDefinitionDir, "pages");
const pageName = "ExecutivePulse";
const pageDir = path.join(pagesDir, pageName);
const visualsDir = path.join(pageDir, "visuals");
const modelDir = path.join(projectRoot, "SF City Pulse.SemanticModel");
const csvPath = path.join(biDir, "sf_city_pulse_powerbi_extract.csv");
const tableName = "BI_NEIGHBORHOOD_DASHBOARD";

const textColumns = new Set([
  "NEIGHBORHOOD",
  "DISTRICT_LABEL",
  "MONTH_LABEL",
  "RESPONSE_TIME_BUCKET",
  "REQUEST_VOLUME_BUCKET",
  "CONSTRUCTION_ACTIVITY_BUCKET",
  "NEIGHBORHOOD_EQUITY_FLAG",
  "DISTRICT_EQUITY_FLAG",
]);

const dateColumns = new Set(["MONTH_START_DATE", "MONTH_END_DATE"]);

const intColumns = new Set([
  "SUPERVISOR_DISTRICT",
  "YEAR",
  "QUARTER",
  "MONTH_NUMBER",
  "MONTH_SORT_KEY",
  "TOTAL_311_REQUESTS",
  "OPEN_REQUEST_COUNT",
  "TOTAL_PERMITS",
  "ACTIVE_PERMIT_COUNT",
  "CITY_TOTAL_311_REQUESTS",
  "CITY_OPEN_REQUEST_COUNT",
  "CITY_TOTAL_PERMITS",
  "DISTRICT_TOTAL_311_REQUESTS",
  "DISTRICT_OPEN_REQUEST_COUNT",
  "DISTRICT_TOTAL_PERMITS",
]);

const currencyColumns = new Set([
  "TOTAL_ESTIMATED_COST",
  "CITY_TOTAL_ESTIMATED_COST",
  "DISTRICT_TOTAL_ESTIMATED_COST",
]);

const percentColumns = new Set([
  "PCT_OPEN_REQUESTS",
  "ACTIVE_PERMIT_SHARE",
  "CITY_PCT_OPEN_REQUESTS",
  "DISTRICT_PCT_OPEN_REQUESTS",
]);

function modelType(name) {
  if (textColumns.has(name)) return "string";
  if (dateColumns.has(name)) return "dateTime";
  if (intColumns.has(name)) return "int64";
  return "double";
}

function summarizeBy(name) {
  if (
    textColumns.has(name) ||
    dateColumns.has(name) ||
    ["YEAR", "QUARTER", "MONTH_NUMBER", "MONTH_SORT_KEY", "SUPERVISOR_DISTRICT"].includes(name)
  ) {
    return "none";
  }

  if (
    name.includes("PCT") ||
    name.includes("SHARE") ||
    name.includes("RATIO") ||
    name.includes("INDEX") ||
    name.includes("AVG") ||
    name.includes("PER_")
  ) {
    return "average";
  }

  return "sum";
}

function formatString(name) {
  if (dateColumns.has(name)) return "Short Date";
  if (currencyColumns.has(name)) return "$#,0;-$#,0;$#,0";
  if (percentColumns.has(name)) return "0.0%";
  if (name.includes("PCT") || name.includes("SHARE")) return "0.0%";
  if (name.includes("AVG") || name.includes("RATIO") || name.includes("INDEX") || name.includes("PER_")) {
    return "0.00";
  }
  if (intColumns.has(name)) return "#,0";
  return undefined;
}

function powerQueryType(name) {
  if (textColumns.has(name)) return "type text";
  if (dateColumns.has(name)) return "type date";
  if (intColumns.has(name)) return "Int64.Type";
  return "type number";
}

async function writeJson(filePath, value) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function sourceRef() {
  return { SourceRef: { Entity: tableName } };
}

function columnRef(name) {
  return { Column: { Expression: sourceRef(), Property: name } };
}

function measureRef(name) {
  return { Measure: { Expression: sourceRef(), Property: name } };
}

function projection(field, queryRef, displayName) {
  return {
    field,
    queryRef: `${tableName}.${queryRef}`,
    displayName,
  };
}

function cardState(measureName) {
  return {
    Values: {
      projections: [projection(measureRef(measureName), measureName, measureName)],
    },
  };
}

function visual(name, visualType, position, queryState) {
  return {
    $schema: "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json",
    name,
    position,
    visual: {
      $schema: "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualConfiguration/2.3.0/schema.json",
      visualType,
      query: { queryState },
    },
    howCreated: "Default",
  };
}

async function main() {
  const csv = await fs.readFile(csvPath, "utf8");
  const headers = csv.split(/\r?\n/, 1)[0].split(",");

  await fs.rm(projectRoot, { recursive: true, force: true });
  await fs.mkdir(visualsDir, { recursive: true });
  await fs.mkdir(modelDir, { recursive: true });

  const columns = headers.map((name) => {
    const column = {
      name,
      dataType: modelType(name),
      sourceColumn: name,
      summarizeBy: summarizeBy(name),
      annotations: [{ name: "SummarizationSetBy", value: "Automatic" }],
    };
    const format = formatString(name);
    if (format) column.formatString = format;
    return column;
  });

  const measures = [
    { name: "Total 311 Requests", expression: `SUM('${tableName}'[TOTAL_311_REQUESTS])`, formatString: "#,0" },
    { name: "Open 311 Requests", expression: `SUM('${tableName}'[OPEN_REQUEST_COUNT])`, formatString: "#,0" },
    { name: "Open Request Share", expression: "DIVIDE([Open 311 Requests], [Total 311 Requests])", formatString: "0.0%" },
    { name: "Total Permits", expression: `SUM('${tableName}'[TOTAL_PERMITS])`, formatString: "#,0" },
    { name: "Active Permits", expression: `SUM('${tableName}'[ACTIVE_PERMIT_COUNT])`, formatString: "#,0" },
    { name: "Total Estimated Cost", expression: `SUM('${tableName}'[TOTAL_ESTIMATED_COST])`, formatString: "$#,0;-$#,0;$#,0" },
    { name: "Avg Days To Close", expression: `AVERAGE('${tableName}'[AVG_DAYS_TO_CLOSE])`, formatString: "0.0" },
    { name: "Avg Response Index Vs City", expression: `AVERAGE('${tableName}'[NEIGHBORHOOD_RESPONSE_INDEX_VS_CITY])`, formatString: "0.00" },
    { name: "Construction To Complaint Ratio", expression: `AVERAGE('${tableName}'[CONSTRUCTION_TO_COMPLAINT_RATIO])`, formatString: "0.00" },
    { name: "Neighborhood Count", expression: `DISTINCTCOUNT('${tableName}'[NEIGHBORHOOD])`, formatString: "#,0" },
  ];

  const typePairs = headers.map((name) => `{"${name}", ${powerQueryType(name)}}`).join(", ");
  const mExpression = [
    "let",
    `    Source = Csv.Document(File.Contents("${path.resolve(csvPath).replaceAll('"', '""')}"), [Delimiter=",", Columns=${headers.length}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),`,
    '    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),',
    `    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {${typePairs}}, "en-US")`,
    "in",
    '    #"Changed Type"',
  ];

  await writeJson(path.join(projectRoot, "SF City Pulse.pbip"), {
    $schema: "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
    version: "1.0",
    artifacts: [{ report: { path: "SF City Pulse.Report" } }],
    settings: { enableAutoRecovery: true },
  });

  await writeJson(path.join(reportDir, "definition.pbir"), {
    $schema: "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
    version: "4.0",
    datasetReference: { byPath: { path: "../SF City Pulse.SemanticModel" } },
  });

  await writeJson(path.join(modelDir, "definition.pbism"), {
    $schema: "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    version: "1.0",
    settings: {},
  });

  await writeJson(path.join(modelDir, "model.bim"), {
    name: "SF City Pulse SemanticModel",
    compatibilityLevel: 1567,
    model: {
      culture: "en-US",
      dataAccessOptions: { legacyRedirects: true, returnErrorValuesAsNull: true },
      defaultPowerBIDataSourceVersion: "powerBI_V3",
      sourceQueryCulture: "en-US",
      tables: [
        {
          name: tableName,
          columns,
          measures,
          partitions: [
            {
              name: tableName,
              mode: "import",
              source: { type: "m", expression: mExpression },
            },
          ],
          annotations: [{ name: "PBI_ResultType", value: "Table" }],
        },
      ],
      annotations: [
        { name: "PBI_QueryOrder", value: `["${tableName}"]` },
        { name: "__PBI_TimeIntelligenceEnabled", value: "0" },
      ],
    },
  });

  await writeJson(path.join(reportDefinitionDir, "version.json"), {
    $schema: "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
    version: "3.3.0",
  });

  await writeJson(path.join(reportDefinitionDir, "report.json"), {
    $schema: "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
    themeCollection: {
      baseTheme: {
        name: "CY25SU05",
        reportVersionAtImport: { visual: "2.9.0", page: "2.1.0", report: "3.3.0" },
        type: "SharedResources",
      },
    },
    reportSource: "Default",
    settings: {
      useEnhancedTooltips: true,
      pagesPosition: "Bottom",
      defaultDisplayUnitsToNone: true,
    },
  });

  await writeJson(path.join(pagesDir, "pages.json"), {
    $schema: "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
    pageOrder: [pageName],
    activePageName: pageName,
  });

  await writeJson(path.join(pageDir, "page.json"), {
    $schema: "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
    name: pageName,
    displayName: "Executive Pulse",
    displayOption: "FitToPage",
    width: 1280,
    height: 720,
    howCreated: "Default",
    annotations: [{ name: "description", value: "SF City Pulse BI dashboard generated from the dbt mart extract." }],
  });

  const visuals = [
    visual("kpiRequests", "card", { x: 32, y: 24, z: 0, width: 280, height: 118, tabOrder: 0 }, cardState("Total 311 Requests")),
    visual("kpiOpenShare", "card", { x: 336, y: 24, z: 1, width: 280, height: 118, tabOrder: 1 }, cardState("Open Request Share")),
    visual("kpiPermits", "card", { x: 640, y: 24, z: 2, width: 280, height: 118, tabOrder: 2 }, cardState("Total Permits")),
    visual("kpiCost", "card", { x: 944, y: 24, z: 3, width: 304, height: 118, tabOrder: 3 }, cardState("Total Estimated Cost")),
    visual("trendRequests", "lineChart", { x: 32, y: 170, z: 4, width: 590, height: 250, tabOrder: 4 }, {
      Category: { projections: [projection(columnRef("MONTH_START_DATE"), "MONTH_START_DATE", "Month")] },
      Y: { projections: [projection(measureRef("Total 311 Requests"), "Total 311 Requests", "Total 311 Requests")] },
    }),
    visual("neighborhoodRequests", "barChart", { x: 658, y: 170, z: 5, width: 590, height: 250, tabOrder: 5 }, {
      Category: { projections: [projection(columnRef("NEIGHBORHOOD"), "NEIGHBORHOOD", "Neighborhood")] },
      Y: { projections: [projection(measureRef("Total 311 Requests"), "Total 311 Requests", "Total 311 Requests")] },
    }),
    visual("dashboardTable", "tableEx", { x: 32, y: 450, z: 6, width: 1216, height: 238, tabOrder: 6 }, {
      Values: {
        projections: [
          projection(columnRef("NEIGHBORHOOD"), "NEIGHBORHOOD", "Neighborhood"),
          projection(columnRef("DISTRICT_LABEL"), "DISTRICT_LABEL", "District"),
          projection(measureRef("Total 311 Requests"), "Total 311 Requests", "Total 311 Requests"),
          projection(measureRef("Open Request Share"), "Open Request Share", "Open Share"),
          projection(measureRef("Avg Days To Close"), "Avg Days To Close", "Avg Days To Close"),
          projection(measureRef("Total Permits"), "Total Permits", "Total Permits"),
          projection(measureRef("Total Estimated Cost"), "Total Estimated Cost", "Estimated Cost"),
          projection(columnRef("NEIGHBORHOOD_EQUITY_FLAG"), "NEIGHBORHOOD_EQUITY_FLAG", "Equity Flag"),
        ],
      },
    }),
  ];

  for (const item of visuals) {
    await writeJson(path.join(visualsDir, item.name, "visual.json"), item);
  }

  console.log(`Created ${path.join(projectRoot, "SF City Pulse.pbip")}`);
  console.log(`Columns: ${headers.length}`);
  console.log(`Visuals: ${visuals.length}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
