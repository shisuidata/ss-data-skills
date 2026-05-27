#!/usr/bin/env node

import { spawnSync } from "node:child_process";

const checks = [
  {
    name: "Library structure",
    command: ["node", "scripts/check-library.mjs"],
  },
  {
    name: "Skill test coverage",
    command: ["node", "scripts/check-tests.mjs"],
  },
  {
    name: "Mock fixture validation",
    command: ["node", "scripts/summarize-ecommerce-fixture.mjs"],
  },
];

function runCheck({ name, command }) {
  console.log(`\n==> ${name}`);
  const result = spawnSync(command[0], command.slice(1), {
    stdio: "inherit",
    shell: false,
  });

  if (result.status !== 0) {
    console.error(`\nPre-push check failed: ${name}`);
    process.exit(result.status ?? 1);
  }
}

for (const check of checks) {
  runCheck(check);
}

runCheck({
  name: "Git whitespace check: working tree",
  command: ["git", "diff", "--check", "HEAD"],
});

const upstream = spawnSync(
  "git",
  ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
  {
    encoding: "utf8",
    shell: false,
  },
);

if (upstream.status === 0) {
  const upstreamRef = upstream.stdout.trim();
  runCheck({
    name: "Git whitespace check: unpushed commits",
    command: ["git", "diff", "--check", `${upstreamRef}..HEAD`],
  });
} else {
  console.log("\n==> Git whitespace check: unpushed commits");
  console.log("No upstream branch configured; skipped unpushed commit diff check.");
}

console.log("\nPre-push check passed. OK to push.");
