---
name: manage-project-memory
description: Initialize, write, update, and validate repository-local project memory under `.codex/docs/memory`, including the `MEMORY.md` routing entry, topic documents, minimal `AGENTS.md` integration, and structural checks. Use when the user explicitly asks to initialize a project memory library, remember or save a durable rule or preference, create or update a memory topic, or validate or repair the memory structure. Never write memory merely because Codex notices a potentially reusable fact; v1 does not implement inbox capture or memory dreaming.
---

# Manage Project Memory

## Core Rules

- Require explicit authorization in the current user request before creating or changing memory content. Treat requests such as “记住这条规则”, “写入 memory”, or “初始化 memory” as authorization.
- Do not treat normal coding, analysis, review, or explanation requests as authorization, even when they reveal reusable information.
- Write authoritative memory only under `.codex/docs/memory/topics/`. Do not write candidates to `inbox/` or `dreams/` in v1.
- Keep memory as a routing and workflow layer, not a substitute for current code, configuration, logs, metrics, checkpoints, or other artifacts.
- Preserve unrelated files and existing memory content. Do not commit or push unless the user explicitly asks.

Read [references/memory-architecture.md](references/memory-architecture.md) completely before initializing memory or writing a topic. Use the bundled scripts without loading their source unless debugging or changing them.

## Locate the Project

1. Resolve the repository root from the user’s target, preferring `git rev-parse --show-toplevel` when available.
2. Pass an absolute repository path to every bundled script.
3. Use only `.codex/docs/memory/` as the memory root.
4. Read the applicable `AGENTS.md` files before any write.

## Initialize Memory

Run initialization only when the user explicitly requests it:

```bash
python <skill-dir>/scripts/init_memory.py --repo-root <absolute-repo-root>
```

The initializer creates the Chinese memory skeleton, future `inbox/` and `dreams/` placeholders, and a minimal root `AGENTS.md` memory section. It preserves existing non-empty memory files, appends rather than replaces project instructions, and does not duplicate an existing `AGENTS.md` reference to `.codex/docs/memory/MEMORY.md`.

After initialization, inspect the created files and run the validator. Do not rewrite an existing memory library merely to make it match the bundled templates.

## Record or Update Memory

1. Restate the durable rule, its intended scope, and the evidence that supports it.
2. Reject temporary runtime state, one-off implementation detail, exact run metrics, transient paths, and unverified historical claims. If no durable rule remains after generalization, explain that and ask the user for a stable formulation instead of writing.
3. Read `.codex/docs/memory/MEMORY.md`, search topic names and content with `rg`, then open only the most relevant one to three topics.
4. Merge into an existing topic when the scope matches. Create a new stable, date-free `snake_case` topic only for a distinct long-lived subject.
5. Follow the eight-section topic structure and writing limits in the architecture reference. Record evidence pointers rather than copying long implementation histories.
6. Update the `MEMORY.md` topic table in the same change. Add a `MEMORY.md` hard rule only when every project task must load it; otherwise keep the rule solely in its topic.
7. Set `最近验证` to the current date and name the concrete verification performed.
8. Run structural validation and inspect the final diff before reporting completion.

## Validate Memory

Run:

```bash
python <skill-dir>/scripts/validate_memory.py --repo-root <absolute-repo-root>
```

Treat errors as required fixes for newly created or modified memory. Treat warnings as review prompts: fix warnings caused by the current change, but do not normalize unrelated legacy memory without authorization.

## Report Results

Report:

- whether memory was initialized, created, or merged;
- the exact topic and `MEMORY.md` paths changed;
- the durable rule that was recorded and its evidence basis;
- validator errors or warnings that remain;
- whether a new task or Codex restart is needed after installing this skill.
