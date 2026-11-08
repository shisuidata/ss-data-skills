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

// 只要键名或取值看起来是明文凭据就拒绝，位置不限于 auth。
const SECRET_KEY = /pass(word|wd|phrase)?|pwd|secret|token|api[-_]?key|access[-_]?key|private[-_]?key|credential|authorization|cookie/i;
const REFERENCE_KEY = /(env|ref|url|uri|endpoint|policy|type|method|name|path|file|ttl|expiry|expires)$/i;
const REFERENCE_VALUE = /^(\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|env:[A-Za-z_][A-Za-z0-9_]*|vault:.+|secretsmanager:.+)$/;
const INLINE_URL_PASSWORD = /[a-z][a-z0-9+.-]*:\/\/[^/\s:@]+:([^/\s@]+)@/i;
const INLINE_AUTH_HEADER = /\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}/i;

function scanForSecrets(value, path) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => scanForSecrets(item, `${path}[${index}]`));
    return;
  }
  if (value && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      const childPath = path ? `${path}.${key}` : key;
      if (typeof child === "string" && child.trim() !== "" && SECRET_KEY.test(key)
        && !REFERENCE_KEY.test(key) && !REFERENCE_VALUE.test(child.trim())) {
        fail(`${childPath} looks like a raw secret; store it in an environment variable and reference the name, for example passwordEnv`);
      }
      scanForSecrets(child, childPath);
    }
    return;
  }
  if (typeof value === "string") {
    const url = value.match(INLINE_URL_PASSWORD);
    if (url && !REFERENCE_VALUE.test(url[1])) {
      fail(`${path} contains a password inside a connection URL; use host and auth fields with env references`);
    }
    if (INLINE_AUTH_HEADER.test(value)) {
      fail(`${path} contains an inline Bearer or Basic credential; use an env reference`);
    }
  }
}

scanForSecrets(config, "");

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
