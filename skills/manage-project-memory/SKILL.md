---
name: manage-project-memory
description: Initialize, write, update, and validate repository-local project memory under the repository-declared memory root (default `.codex/docs/memory`), including the `MEMORY.md` routing entry, machine-readable topic frontmatter, topic documents, minimal `AGENTS.md` integration, and structural checks. Use when the user explicitly asks to initialize a project memory library, remember or save a durable rule or preference, create or update a memory topic, or validate or repair the memory structure. Never write memory merely because Codex notices a potentially reusable fact; v1 does not implement inbox capture or memory dreaming.
---

# Manage Project Memory

## Core Rules

- Require explicit authorization in the current user request before creating or changing memory content. Treat requests such as “记住这条规则”, “写入 memory”, or “初始化 memory” as authorization.
- Do not treat normal coding, analysis, review, or explanation requests as authorization, even when they reveal reusable information.
- Write authoritative memory only under `<memory-root>/topics/`. The default root is `.codex/docs/memory`; preserve a different existing root when the repository's `AGENTS.md` declares one. Do not write candidates to `inbox/` or `dreams/` in v1.
- Keep memory as a routing and workflow layer, not a substitute for current code, configuration, logs, metrics, checkpoints, or other artifacts.
- Preserve unrelated files and existing memory content. Do not commit or push unless the user explicitly asks.

Read [references/memory-architecture.md](references/memory-architecture.md) completely before initializing memory or writing a topic. Use the bundled scripts without loading their source unless debugging or changing them.

## Locate the Project

1. Resolve the repository root from the user’s target, preferring `git rev-parse --show-toplevel` when available.
2. Pass an absolute repository path to every bundled script.
3. Read the applicable `AGENTS.md` files before any write and resolve the repository's declared memory entry. Use `.codex/docs/memory/` only when the repository has no existing declaration.
4. Pass the resolved repository-relative root to bundled scripts with `--memory-root`; do not migrate an established memory library merely to match the default.

## Initialize Memory

Run initialization only when the user explicitly requests it:

```bash
python <skill-dir>/scripts/init_memory.py --repo-root <absolute-repo-root> [--memory-root <repo-relative-memory-root>]
```

The initializer creates the Chinese memory skeleton, future `inbox/` and `dreams/` placeholders, and a minimal root `AGENTS.md` memory section for the resolved root. It preserves existing non-empty memory files, appends rather than replaces project instructions, and does not duplicate an existing `AGENTS.md` reference to that memory entry. If its managed block already points to another root, initialization fails before writing instead of creating a second library.

After initialization, inspect the created files and run the validator. Do not rewrite an existing memory library merely to make it match the bundled templates.

## Record or Update Memory

1. Restate the durable rule, its intended scope, and the evidence that supports it.
2. Reject temporary runtime state, one-off implementation detail, exact run metrics, transient paths, and unverified historical claims. If no durable rule remains after generalization, explain that and ask the user for a stable formulation instead of writing.
3. Read `<memory-root>/MEMORY.md`, batch-inspect only the frontmatter of indexed topics, and match `description`, triggers, status, and path hints before opening the most relevant one to three bodies.
4. Merge into an existing topic when the scope matches. Create a new stable, date-free `snake_case` topic only for a distinct long-lived subject.
5. Add the required flat YAML frontmatter fields: `id`, `description`, `positive_triggers`, `negative_triggers`, `paths`, `status`, and `last_verified`. Treat frontmatter as the canonical machine-readable routing metadata; keep `paths` as relevance hints, not unconditional load rules.
6. Follow the six-section topic body and writing limits in the architecture reference. Do not add separate `范围` or `触发词` sections; routing belongs only in frontmatter. Record evidence pointers rather than copying long implementation histories.
7. Update the path-only `MEMORY.md` topic index in the same change. Add a `MEMORY.md` hard rule only when every project task must load it; otherwise keep the rule solely in its topic.
8. Set both frontmatter `last_verified` and the `最近验证` section to the current date and name the concrete verification performed. Use `status: needs_review` with `last_verified: null` when no real verification has occurred; never advance the date for a formatting-only change.
9. Run structural validation and inspect the final diff before reporting completion.

## Validate Memory

Run:

```bash
python <skill-dir>/scripts/validate_memory.py --repo-root <absolute-repo-root> [--memory-root <repo-relative-memory-root>]
```

Treat errors as required fixes for newly created or modified memory. Treat warnings as review prompts: fix warnings caused by the current change, but do not normalize unrelated legacy memory without authorization.

The validator checks the path-only index and machine-readable topic structure. It cannot determine whether the chosen trigger phrases cover every intended user expression; inspect semantic coverage in the final diff.

## Report Results

Report:

- whether memory was initialized, created, or merged;
- the resolved memory root and exact topic and `MEMORY.md` paths changed;
- the durable rule that was recorded and its evidence basis;
- validator errors or warnings that remain;
- whether a new task or Codex restart is needed after installing this skill.
