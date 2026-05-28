#!/usr/bin/env node

import { readFileSync } from "node:fs";

const allowedToolTypes = new Set([
  "database",
  "api",
  "bi",
  "workflow",
  "storage",
  "message",
  "other",
]);

function fail(message) {
  console.error(`Invalid integration config: ${message}`);
  process.exit(1);
}

function requireString(value, path) {
  if (typeof value !== "string" || value.trim() === "") {
    fail(`${path} must be a non-empty string`);
  }
}

function requireObject(value, path) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    fail(`${path} must be an object`);
  }
}

const configPath = process.argv[2];
if (!configPath) {
  fail("usage: validate_integration_config.mjs <config.json>");
}

let config;
try {
  config = JSON.parse(readFileSync(configPath, "utf8"));
} catch (error) {
  fail(`cannot read or parse JSON: ${error.message}`);
}

requireString(config.toolName, "toolName");
requireString(config.toolType, "toolType");
if (!allowedToolTypes.has(config.toolType)) {
  fail(`toolType must be one of ${Array.from(allowedToolTypes).join(", ")}`);
}
requireString(config.owner, "owner");
requireString(config.environment, "environment");
requireObject(config.connection, "connection");

if (config.toolType === "database") {
  requireString(config.connection.engine, "connection.engine");
  requireString(config.connection.host, "connection.host");
  if (typeof config.connection.port !== "number") {
    fail("connection.port must be a number");
  }
  requireString(config.connection.database, "connection.database");
}

if (config.toolType === "api") {
  requireString(config.connection.baseUrl, "connection.baseUrl");
}

requireObject(config.auth, "auth");
requireString(config.auth.method, "auth.method");

if (config.auth.password || config.auth.token || config.auth.secret) {
  fail("auth must not contain raw password, token, or secret values; use env names instead");
}

if (config.auth.method === "password") {
  requireString(config.auth.usernameEnv, "auth.usernameEnv");
  requireString(config.auth.passwordEnv, "auth.passwordEnv");
}

if (config.auth.method === "token") {
  requireString(config.auth.tokenEnv, "auth.tokenEnv");
}

if (config.permissions) {
  requireObject(config.permissions, "permissions");
  if (config.permissions.mode) {
    requireString(config.permissions.mode, "permissions.mode");
  }
}

console.log("Integration config validation passed.");
