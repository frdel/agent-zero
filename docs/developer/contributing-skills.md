# Contributing Skills to Agent Zero

Welcome to the Agent Zero Skills ecosystem! This guide will help you create, test, and share skills with the community.

---

## What is a Skill?

A **Skill** is a contextual expertise module that provides the AI agent with specialized knowledge and procedures for specific tasks. Unlike tools (which are always loaded), skills are **surfaced via description/tag matching** when relevant, making them token-efficient and context-aware.

### Skills vs Tools vs Knowledge

| Aspect | Skills | Tools | Knowledge |
|--------|--------|-------|-----------|
| **Loading** | Description/tag matching | Always in prompt | Semantic recall |
| **Purpose** | Procedures & expertise | Actions & functions | Facts & data |
| **Format** | SKILL.md (YAML + Markdown) | Python/code | Text/documents |
| **When to use** | "How to do X" | "Do X now" | "What is X" |

### Cross-Platform Compatibility

The SKILL.md standard is compatible with:
- **Agent Zero** (this project)
- **Claude Code** (Anthropic)
- **Cursor** (AI IDE)
- **OpenAI Codex CLI**
- **GitHub Copilot**
- **Goose** (Block)

Skills you create here can be used in any of these platforms!

---

## Quick Start

### Using the CLI (Recommended)

```bash
# Create a new skill interactively
python -m helpers.skills_cli create my-skill-name

# List all available skills
python -m helpers.skills_cli list

# Validate a skill
python -m helpers.skills_cli validate my-skill-name

# Search skills
python -m helpers.skills_cli search "keyword"
```

### Manual Creation

1. Create a folder in `usr/skills/` with your skill name
2. Add a `SKILL.md` file with YAML frontmatter
3. Optionally add supporting scripts (`.py`, `.sh`, `.js`)

---

## SKILL.md Standard

Every skill must have a `SKILL.md` file with this structure:

```markdown
---
name: "skill-name"
description: "A clear, concise description of what this skill does and when to use it"
version: "1.0.0"
author: "Your Name <email@example.com>"
license: "MIT"
tags: ["category", "purpose", "technology"]
triggers:
  - "keyword that activates this skill"
  - "another trigger phrase"
allowed_tools:
  - tool_name
  - another_tool
metadata:
  complexity: "beginner|intermediate|advanced"
  category: "development|devops|data|productivity|creative"
  estimated_time: "5 minutes"
---

# Skill Name

## Overview

Brief description of what this skill accomplishes.

## When to Use

- Situation 1 where this skill applies
- Situation 2 where this skill applies

## Instructions

### Step 1: First Step

Detailed instructions...

### Step 2: Second Step

More instructions...

## Examples

### Example 1: Basic Usage

\`\`\`python
# Code example
\`\`\`

### Example 2: Advanced Usage

\`\`\`python
# Advanced code example
\`\`\`

## Common Pitfalls

- Pitfall 1 and how to avoid it
- Pitfall 2 and how to avoid it

## Related Skills

- `related-skill-1`
- `related-skill-2`
```

### Required Fields

| Field | Description |
|-------|-------------|
| `name` | Unique identifier (lowercase, hyphens allowed) |
| `description` | What the skill does (used for semantic matching) |

### Optional Fields

| Field | Description |
|-------|-------------|
| `version` | Semantic version (e.g., "1.0.0") |
| `author` | Your name and email |
| `license` | License (MIT, Apache-2.0, etc.) |
| `tags` | Categories for discovery |
| `triggers` | Phrases that activate this skill |
| `allowed_tools` | Tools this skill can use |
| `metadata` | Additional structured data |

---

## Creating Your First Skill

### Step 1: Identify the Need

Ask yourself:
- What expertise would help the agent?
- When should this skill be activated?
- What steps should the agent follow?

### Step 2: Create the Structure

```bash
# Using CLI
python -m helpers.skills_cli create my-awesome-skill

# Or manually
mkdir -p usr/skills/my-awesome-skill
touch usr/skills/my-awesome-skill/SKILL.md
```

### Step 3: Write the SKILL.md

```markdown
---
name: "my-awesome-skill"
description: "Helps with [specific task] when [specific situation]"
version: "1.0.0"
author: "Your Name"
tags: ["category"]
---

# My Awesome Skill

## When to Use

Use this skill when you need to [specific task].

## Instructions

1. First, do this...
2. Then, do that...
3. Finally, verify by...

## Examples

### Example: Basic Case

[Show a complete example]
```

### Step 4: Add Supporting Files (Optional)

If your skill needs scripts:

```
my-awesome-skill/
├── SKILL.md           # Required
├── helper.py          # Optional Python script
├── setup.sh           # Optional shell script
└── templates/         # Optional templates folder
    └── config.json
```

Reference them in your SKILL.md:

```markdown
## Scripts

This skill includes helper scripts:
- `helper.py` - Does X
- `setup.sh` - Sets up Y
```

### Step 5: Test Your Skill

```bash
# Validate the skill
python -m helpers.skills_cli validate my-awesome-skill

# Test in Agent Zero
# Start the agent and ask it to perform the task your skill handles
```

---

## Best Practices

### Writing Effective Descriptions

The `description` field is crucial for semantic matching. Make it:

**Good:**
```yaml
description: "Guides systematic debugging of Python applications using print statements, debugger, and logging to identify root causes"
```

**Bad:**
```yaml
description: "Helps with debugging"
```

### Structuring Instructions

1. **Be Specific** - Avoid vague instructions
2. **Use Steps** - Number your steps clearly
3. **Include Examples** - Show, don't just tell
4. **Anticipate Errors** - Include troubleshooting

### Semantic Triggers

Design your description and content so the skill is recalled when relevant:

```yaml
# Include synonyms and related terms
description: "Helps create REST APIs, web services, HTTP endpoints, and backend routes using FastAPI, Flask, or Express"
```

### Keep Skills Focused

One skill = one expertise area. If your skill is getting too long, split it:

- `api-design` - API structure and patterns
- `api-security` - API authentication and authorization
- `api-testing` - API testing strategies

---

## Testing Skills

### Local Testing

1. **Validate Structure:**
   ```bash
   python -m helpers.skills_cli validate my-skill
   ```

2. **Test Semantic Recall:**
   Start Agent Zero and ask questions that should trigger your skill.

3. **Verify Instructions:**
   Follow your own instructions manually to ensure they work.

---

## Sharing Skills

### Contributing to Agent Zero

1. **Fork the Repository:**
   ```bash
   git clone https://github.com/agent0ai/agent-zero.git
   cd agent-zero
   ```

2. **Create Your Skill:**
   ```bash
   python -m helpers.skills_cli create my-skill
   # Edit usr/skills/my-skill/SKILL.md
   ```

3. **Move to Bundled Collection (for contribution):**
   ```bash
   mv usr/skills/my-skill plugins/_skills/skills/my-skill
   ```

4. **Create a Pull Request:**
   - Branch: `feat/skill-my-skill-name`
   - Title: `feat(skills): add my-skill-name skill`
   - Description: Explain what the skill does and why it's useful

### Publishing Skills

Share your skills on [skillsmp.com](https://skillsmp.com) or [skills.sh](https://skills.sh):

1. Create a GitHub repository for your skill
2. Ensure it follows the SKILL.md standard
3. Submit via their contribution process

### Creating a Skills Collection

For multiple related skills, create a repository:

```
my-skills-collection/
├── README.md
├── skills/
│   ├── skill-1/
│   │   └── SKILL.md
│   ├── skill-2/
│   │   └── SKILL.md
│   └── skill-3/
│       └── SKILL.md
└── LICENSE
```

---

## Community Guidelines

### Quality Standards

- **Tested** - Skills must be tested before submission
- **Documented** - Clear instructions and examples
- **Focused** - One expertise per skill
- **Original** - Don't duplicate existing skills

### Naming Conventions

- Use lowercase with hyphens: `my-skill-name`
- Be descriptive: `python-debugging` not `debug`
- Avoid generic names: `fastapi-crud` not `api`

### License

- Include a license (MIT recommended for maximum compatibility)
- Respect licenses of any code you include
- Don't include proprietary or copyrighted content

---

## FAQ

### Q: Where should I put my skills?

**A:** During development, use `usr/skills/`. For contribution, move to `plugins/_skills/skills/`.

### Q: How are skills discovered?

**A:** Skills are matched against their name, description, and tags for the current query. They are not indexed into vector memory.

### Q: Can I use skills from other platforms?

**A:** Yes! The SKILL.md standard is cross-platform. Skills from Claude Code, Cursor, or other compatible platforms can be copied directly to `usr/skills/`.

### Q: How do I update a skill?

**A:** Edit the SKILL.md file and increment the version number. Changes take effect on agent restart.

### Q: Can skills call other skills?

**A:** Skills don't directly call each other, but the agent may combine multiple skills when appropriate for a task.

---

Happy skill building! 🚀
