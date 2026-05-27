#!/usr/bin/env node

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const skillsDir = join(root, "skills");
const examplesDir = join(root, "examples");

const errors = [];

function listSkillDirs() {
  return readdirSync(skillsDir)
    .filter((name) => name !== "_template")
    .filter((name) => statSync(join(skillsDir, name)).isDirectory())
    .sort();
}

function readSkillName(skillDir) {
  const skillPath = join(skillsDir, skillDir, "SKILL.md");
  if (!existsSync(skillPath)) {
    errors.push(`Missing SKILL.md: skills/${skillDir}/SKILL.md`);
    return null;
  }

  const content = readFileSync(skillPath, "utf8");
  const match = content.match(/^name:\s*(.+)$/m);
  if (!match) {
    errors.push(`Missing frontmatter name: skills/${skillDir}/SKILL.md`);
    return null;
  }

  return match[1].trim();
}

for (const skillDir of listSkillDirs()) {
  const skillName = readSkillName(skillDir);
  if (!skillName) continue;

  if (skillName !== skillDir) {
    errors.push(`Skill name mismatch: directory=${skillDir}, name=${skillName}`);
  }

  const examplePath = join(examplesDir, `${skillDir}.md`);
  if (!existsSync(examplePath)) {
    errors.push(`Missing example: examples/${skillDir}.md`);
  }
}

const requiredDocs = [
  "README.md",
  "SKILL_INDEX.md",
  "CONTEXT_GUIDE.md",
  "CONTRIBUTING.md",
  "examples/README.md",
  "context/README.md",
];

for (const doc of requiredDocs) {
  if (!existsSync(join(root, doc))) {
    errors.push(`Missing required doc: ${doc}`);
  }
}

const requiredContextTemplates = [
  "data-task-context.md",
  "metric-context.md",
  "table-context.md",
  "sql-review-context.md",
  "analysis-context.md",
  "experiment-context.md",
  "report-context.md",
  "presentation-context.md",
];

for (const template of requiredContextTemplates) {
  const path = join(root, "context", "templates", template);
  if (!existsSync(path)) {
    errors.push(`Missing context template: context/templates/${template}`);
  }
}

if (errors.length > 0) {
  console.error("Library check failed:\n");
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log("Library check passed.");
console.log(`Skills: ${listSkillDirs().length}`);
console.log(`Context templates: ${requiredContextTemplates.length}`);

