#!/usr/bin/env node

import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const fixtureDir = join(root, "tests", "fixtures", "ecommerce-growth");

function parseCsv(path) {
  const lines = readFileSync(path, "utf8").trim().split(/\r?\n/);
  const headers = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const values = line.split(",");
    return Object.fromEntries(headers.map((header, index) => [header, values[index]]));
  });
}

function inRange(dt, start, end) {
  return dt >= start && dt <= end;
}

function countDistinct(rows, key) {
  return new Set(rows.map((row) => row[key])).size;
}

function summarizePeriod({ name, start, end }, registers, events, orders) {
  const periodRegisters = registers.filter((row) => inRange(row.dt, start, end));
  const periodEvents = events.filter((row) => inRange(row.dt, start, end));
  const periodOrders = orders.filter((row) => inRange(row.dt, start, end) && row.pay_status === "success");

  const eventUsers = (eventName) =>
    countDistinct(periodEvents.filter((row) => row.event_name === eventName), "user_id");

  const summary = {
    name,
    registered: countDistinct(periodRegisters, "user_id"),
    productView: eventUsers("product_view"),
    addToCart: eventUsers("add_to_cart"),
    orderSubmit: eventUsers("order_submit"),
    paySuccess: countDistinct(periodOrders, "user_id"),
  };

  summary.payRate = summary.registered === 0 ? 0 : summary.paySuccess / summary.registered;
  return summary;
}

const registers = parseCsv(join(fixtureDir, "dwd_user_register_d.csv"));
const events = parseCsv(join(fixtureDir, "dwd_user_event_d.csv"));
const orders = parseCsv(join(fixtureDir, "dwd_order_detail_d.csv"));

const periods = [
  { name: "previous", start: "2026-04-17", end: "2026-04-30" },
  { name: "current", start: "2026-05-01", end: "2026-05-14" },
];

const summaries = periods.map((period) => summarizePeriod(period, registers, events, orders));

const expected = {
  previous: { registered: 12, productView: 10, addToCart: 7, orderSubmit: 5, paySuccess: 4 },
  current: { registered: 12, productView: 9, addToCart: 5, orderSubmit: 3, paySuccess: 2 },
};

const errors = [];
for (const summary of summaries) {
  const target = expected[summary.name];
  for (const [key, expectedValue] of Object.entries(target)) {
    if (summary[key] !== expectedValue) {
      errors.push(`${summary.name}.${key}: expected ${expectedValue}, got ${summary[key]}`);
    }
  }
}

console.log("Ecommerce fixture summary:");
for (const summary of summaries) {
  console.log(
    `${summary.name}: registered=${summary.registered}, product_view=${summary.productView}, add_to_cart=${summary.addToCart}, order_submit=${summary.orderSubmit}, pay_success=${summary.paySuccess}, pay_rate=${(summary.payRate * 100).toFixed(1)}%`,
  );
}

if (errors.length > 0) {
  console.error("\nFixture validation failed:");
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log("Fixture validation passed.");
