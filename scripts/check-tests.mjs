#!/usr/bin/env node

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const testsDir = join(root, "tests");
const casesDir = join(testsDir, "cases");
const skillsDir = join(root, "skills");
const fixturesDir = join(testsDir, "fixtures", "ecommerce-growth");
const rubricsDir = join(testsDir, "rubrics");

const errors = [];

const requiredTopLevel = [
  "tests/README.md",
  "tests/rubrics/common.md",
  "tests/fixtures/ecommerce-growth/README.md",
  "tests/fixtures/ecommerce-growth/expected-summary.md",
];

const requiredFixtures = [
  "dwd_user_register_d.csv",
  "dwd_user_event_d.csv",
  "dwd_order_detail_d.csv",
  "bad_conversion_sql.sql",
  "expected-summary.md",
];

const requiredCaseSections = [
  "## Skill",
  "## 测试目标",
  "## 测试输入",
  "## 通过标准",
];

function fail(message) {
  errors.push(message);
}

function listSkillDirs() {
  return readdirSync(skillsDir)
    .filter((name) => name !== "_template")
    .filter((name) => statSync(join(skillsDir, name)).isDirectory())
    .sort();
}

for (const path of requiredTopLevel) {
  if (!existsSync(join(root, path))) {
    fail(`Missing required test file: ${path}`);
  }
}

for (const fixture of requiredFixtures) {
  if (!existsSync(join(fixturesDir, fixture))) {
    fail(`Missing fixture: tests/fixtures/ecommerce-growth/${fixture}`);
  }
}

if (!existsSync(casesDir)) {
  fail("Missing tests/cases directory");
} else {
  const cases = readdirSync(casesDir)
    .filter((name) => name.endsWith(".md"))
    .sort();
  const caseNames = new Set(cases.map((name) => name.replace(/\.md$/, "")));

  if (cases.length === 0) {
    fail("No test cases found in tests/cases");
  }

  for (const skill of listSkillDirs()) {
    if (!caseNames.has(skill)) {
      fail(`Missing test case for skill "${skill}": tests/cases/${skill}.md`);
    }
  }

  for (const file of cases) {
    const path = join(casesDir, file);
    if (!statSync(path).isFile()) continue;
    const content = readFileSync(path, "utf8");

    for (const section of requiredCaseSections) {
      if (!content.includes(section)) {
        fail(`Missing section "${section}": tests/cases/${file}`);
      }
    }

    const skill = content.match(/## Skill\s+`([^`]+)`/m)?.[1];
    if (!skill) {
      fail(`Cannot parse skill name: tests/cases/${file}`);
    } else if (!existsSync(join(root, "skills", skill, "SKILL.md"))) {
      fail(`Test case references missing skill "${skill}": tests/cases/${file}`);
    }

    if (!content.includes("```text")) {
      fail(`Test input should use a text code block: tests/cases/${file}`);
    }
  }
}

if (!existsSync(join(rubricsDir, "common.md"))) {
  fail("Missing common rubric: tests/rubrics/common.md");
}

if (errors.length > 0) {
  console.error("Test check failed:\n");
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log("Test check passed.");
console.log(`Cases: ${readdirSync(casesDir).filter((name) => name.endsWith(".md")).length}`);
console.log(`Skills covered: ${listSkillDirs().length}`);
console.log(`Fixtures: ${requiredFixtures.length}`);
