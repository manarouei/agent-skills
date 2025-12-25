# Node Implementation Skills

A collection of [Agent Skills](https://agentskills.io/) for autonomous workflow node implementation.

## Overview

These skills enable AI agents to implement workflow nodes from TypeScript source code or API documentation. The skills follow the [Agent Skills specification](https://agentskills.io/specification) and can be used with any compatible agent runtime.

## Skills

| Skill | Description |
|-------|-------------|
| [node-normalize](skills/node-normalize/) | Normalize node names and generate correlation IDs |
| [source-classify](skills/source-classify/) | Classify source as Type1 (TypeScript) or Type2 (documentation) |
| [source-ingest](skills/source-ingest/) | Fetch and bundle source materials |
| [schema-infer](skills/schema-infer/) | Extract operations, parameters, and credentials from source |
| [schema-build](skills/schema-build/) | Build BaseNode-compliant schema |
| [node-scaffold](skills/node-scaffold/) | Generate Python class skeleton |
| [code-convert](skills/code-convert/) | Convert TypeScript to Python (Type1) |
| [code-implement](skills/code-implement/) | Implement from documentation using LLM (Type2) |
| [test-generate](skills/test-generate/) | Generate pytest test suite |
| [code-validate](skills/code-validate/) | Run tests and static analysis |
| [code-fix](skills/code-fix/) | Attempt automated fixes for failures |
| [pr-prepare](skills/pr-prepare/) | Package artifacts for PR submission |

## Usage

### With Claude Code

```bash
# Add this repository as a skill source
/skill add /path/to/agent-skills/skills

# Use a skill
"Use the node-normalize skill to normalize 'Telegram Bot' as a node name"
```

### With Claude.ai

Upload the skill folders to Claude.ai following the [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude) guide.

### Pipeline Flow

```
node-normalize → source-classify → source-ingest → schema-infer → schema-build → node-scaffold
                                                                                      ↓
                                              [TYPE1: code-convert] OR [TYPE2: code-implement]
                                                                                      ↓
                                              test-generate → code-validate ↔ code-fix → pr-prepare
```

## Skill Format

Each skill follows the [Agent Skills specification](https://agentskills.io/specification):

```
skill-name/
└── SKILL.md    # Required: frontmatter + instructions
```

### SKILL.md Format

```markdown
---
name: skill-name
description: What the skill does and when to use it.
---

# Skill Name

Instructions for the agent...
```

## Validation

Use the [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref) library to validate skills:

```bash
skills-ref validate ./skills/node-normalize
```

## License

Apache-2.0

## Related

- [Agent Skills Specification](https://agentskills.io/specification)
- [Example Skills](https://github.com/anthropics/skills)
- [Agent Skills GitHub](https://github.com/agentskills/agentskills)
