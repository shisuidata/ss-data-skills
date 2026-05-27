#!/usr/bin/env node

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const skillsDir = join(root, "skills");
const examplesDir = join(root, "examples");
const catalogPath = join(skillsDir, "catalog.json");

const errors = [];
const warnings = [];

const requiredSkillSections = [
  "## 目标",
  "## 使用场景",
  "## 不适用场景",
  "## 输入信息",
  "## 上下文建议",
  "## 输出格式",
  "## 质量标准",
  "## 示例 Prompt",
];

const requiredExampleSections = [
  "## 适用场景",
  "## 示例输入",
  "## 预期输出",
  "## 使用说明",
];

function listSkillDirs() {
  return readdirSync(skillsDir)
    .filter((name) => name !== "_template")
    .filter((name) => statSync(join(skillsDir, name)).isDirectory())
    .sort();
}

function readSkill(skillDir) {
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

  return {
    content,
    name: match[1].trim(),
    path: skillPath,
  };
}

for (const skillDir of listSkillDirs()) {
  const skill = readSkill(skillDir);
  if (!skill) continue;

  if (skill.name !== skillDir) {
    errors.push(`Skill name mismatch: directory=${skillDir}, name=${skill.name}`);
  }

  const description = skill.content.match(/^description:\s*(.+)$/m)?.[1]?.trim();
  if (!description) {
    errors.push(`Missing frontmatter description: skills/${skillDir}/SKILL.md`);
  } else if (!description.startsWith("Use when ")) {
    warnings.push(`Description should start with "Use when": skills/${skillDir}/SKILL.md`);
  }

  for (const section of requiredSkillSections) {
    if (!skill.content.includes(section)) {
      errors.push(`Missing section "${section}": skills/${skillDir}/SKILL.md`);
    }
  }

  if (!skill.content.includes("../../context/templates/")) {
    warnings.push(`No context template link found: skills/${skillDir}/SKILL.md`);
  }

  const examplePath = join(examplesDir, `${skillDir}.md`);
  if (!existsSync(examplePath)) {
    errors.push(`Missing example: examples/${skillDir}.md`);
  } else {
    const example = readFileSync(examplePath, "utf8");
    for (const section of requiredExampleSections) {
      if (!example.includes(section)) {
        errors.push(`Missing section "${section}": examples/${skillDir}.md`);
      }
    }
    if (!example.includes(`请用 ${skillDir}`) && !example.includes(`使用 ${skillDir}`)) {
      warnings.push(`Example may not show direct skill invocation: examples/${skillDir}.md`);
    }
  }
}

if (!existsSync(catalogPath)) {
  errors.push("Missing skill catalog: skills/catalog.json");
} else {
  let catalog;
  try {
    catalog = JSON.parse(readFileSync(catalogPath, "utf8"));
  } catch (error) {
    errors.push(`Invalid JSON in skills/catalog.json: ${error.message}`);
  }

  if (catalog) {
    const catalogSkills = Array.isArray(catalog.skills) ? catalog.skills : [];
    const catalogIds = new Set(catalogSkills.map((skill) => skill.id));

    for (const skillDir of listSkillDirs()) {
      if (!catalogIds.has(skillDir)) {
        errors.push(`Missing skill in catalog: ${skillDir}`);
      }
    }

    for (const skill of catalogSkills) {
      if (!skill.id || !existsSync(join(skillsDir, skill.id, "SKILL.md"))) {
        errors.push(`Catalog references missing skill: ${skill.id ?? "(missing id)"}`);
      }
      if (!skill.displayName) {
        errors.push(`Catalog skill missing displayName: ${skill.id}`);
      }
      if (!skill.category) {
        errors.push(`Catalog skill missing category: ${skill.id}`);
      }
    }
  }
}

const requiredDocs = [
  "README.md",
  "QUICK_START.md",
  "SOP.md",
  "SKILL_INDEX.md",
  "CONTEXT_GUIDE.md",
  "CONTRIBUTING.md",
  "TESTING.md",
  "docs/testing-standard.md",
  "docs/skill-development-workflow.md",
  "docs/templates/skill-brief.md",
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

const expectedLinks = [
  ["README.md", "QUICK_START.md"],
  ["README.md", "SKILL_INDEX.md"],
  ["README.md", "SOP.md"],
  ["README.md", "CONTEXT_GUIDE.md"],
  ["README.md", "docs/testing-standard.md"],
  ["README.md", "examples/README.md"],
  ["README.md", "CONTRIBUTING.md"],
  ["SKILL_INDEX.md", "context/README.md"],
  ["CONTRIBUTING.md", "SOP.md"],
  ["CONTRIBUTING.md", "CONTEXT_GUIDE.md"],
  ["TESTING.md", "SOP.md"],
  ["TESTING.md", "docs/testing-standard.md"],
  ["skills/README.md", "../CONTEXT_GUIDE.md"],
];

for (const [file, link] of expectedLinks) {
  const path = join(root, file);
  if (!existsSync(path)) continue;
  const content = readFileSync(path, "utf8");
  if (!content.includes(link)) {
    errors.push(`Missing expected link "${link}" in ${file}`);
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
if (warnings.length > 0) {
  console.log(`Warnings: ${warnings.length}`);
  for (const warning of warnings) {
    console.log(`- ${warning}`);
  }
}
