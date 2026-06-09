#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [jsonPathArg] = process.argv.slice(2);
if (!jsonPathArg) {
  console.error("Usage: node tax_workflow_tool/build_workbook.mjs <workflow_result.json>");
  process.exit(1);
}

const jsonPath = path.resolve(jsonPathArg);
const outDir = path.dirname(jsonPath);
const data = JSON.parse(await fs.readFile(jsonPath, "utf8"));

const workbook = Workbook.create();
const finalSheet = workbook.worksheets.add("最终输出");
const workflowSheet = workbook.worksheets.add("筛选口径");
const currencySheet = workbook.worksheets.add("币种汇总");
const detailSheet = workbook.worksheets.add("命中明细");

function writeTable(sheet, startCell, headers, rows) {
  const values = [headers, ...rows.map((row) => headers.map((header) => row[header] ?? ""))];
  const range = sheet.getRange(startCell).resize(values.length, headers.length);
  range.values = values;
  range.format = { wrapText: true };
  sheet.getRange(startCell).resize(1, headers.length).format = {
    fill: "#1F4E78",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  range.format.autofitColumns();
}

finalSheet.showGridLines = false;
finalSheet.getRange("A1:E1").merge();
finalSheet.getRange("A1").values = [["A1-A3未代扣代缴工作流输出"]];
finalSheet.getRange("A1").format = {
  fill: "#17365D",
  font: { bold: true, color: "#FFFFFF", size: 16 },
};
finalSheet.getRange("A3:B8").values = [
  ["算税月", data.activity_period],
  ["算税国家", data.tax_country],
  ["源文件", data.source_file],
  ["已注册税号国家", data.registered_vat_countries.join(", ")],
  ["未注册欧盟国家", data.unregistered_eu_countries.join(", ")],
  ["当月汇率", Object.entries(data.rates_for_month).map(([k, v]) => `${k}:${v ?? "未填"}`).join(", ")],
];
finalSheet.getRange("A3:A8").format = { fill: "#D9EAF7", font: { bold: true } };
finalSheet.getRange("B3:B8").format = { wrapText: true };
writeTable(finalSheet, "A10", ["A项", "名称", "命中行数", "EUR金额总和", "缺少汇率行数"], data.summary);
writeTable(finalSheet, "A16", ["项目", "公式", "金额EUR"], data.final);
finalSheet.getRange("D11:D13").format.numberFormat = "#,##0.00";
finalSheet.getRange("C17:C18").format.numberFormat = "#,##0.00";
finalSheet.freezePanes.freezeRows(10);

writeTable(workflowSheet, "A1", ["A项", "名称", "筛选口径", "金额列"], data.summary);
workflowSheet.freezePanes.freezeRows(1);

writeTable(currencySheet, "A1", ["A项", "币种", "行数", "原币合计", "折EUR金额", "缺少汇率行数"], data.currency);
currencySheet.getRange("D2:E200").format.numberFormat = "#,##0.00";
currencySheet.freezePanes.freezeRows(1);

const detailHeaders = [
  "A项",
  "A项名称",
  "ACTIVITY_PERIOD",
  "TAX_COLLECTION_RESPONSIBILITY",
  "TRANSACTION_TYPE",
  "EXPORT_OUTSIDE_EU",
  "PRICE_OF_ITEMS_VAT_RATE_PERCENT",
  "SALE_DEPART_COUNTRY",
  "SALE_ARRIVAL_COUNTRY",
  "BUYER_VAT_NUMBER",
  "TRANSACTION_CURRENCY_CODE",
  "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL",
  "_original_amount",
  "_eur_amount",
  "TRANSACTION_EVENT_ID",
  "ACTIVITY_TRANSACTION_ID",
];
writeTable(detailSheet, "A1", detailHeaders, data.detail);
detailSheet.getRange("L2:N5000").format.numberFormat = "#,##0.00";
detailSheet.freezePanes.freezeRows(1);

for (const sheet of [finalSheet, workflowSheet, currencySheet, detailSheet]) {
  sheet.getUsedRange().format.autofitColumns();
}

const check = await workbook.inspect({
  kind: "table",
  range: "最终输出!A1:E18",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 8,
});
console.log(check.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const preview = await workbook.render({
  sheetName: "最终输出",
  autoCrop: "all",
  scale: 1,
  format: "png",
});
await fs.writeFile(path.join(outDir, "最终输出.png"), new Uint8Array(await preview.arrayBuffer()));

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
const xlsxPath = path.join(outDir, `A1-A3未代扣代缴输出_${data.activity_period}.xlsx`);
await xlsx.save(xlsxPath);
console.log(xlsxPath);
