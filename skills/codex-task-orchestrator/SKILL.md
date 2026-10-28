---
name: codex-task-orchestrator
description: Use when the user wants Codex to act as a principal agent that turns a lightweight task request into a plan-reviewed, multi-agent implementation and validation workflow. This skill reads a task document plus principal-agent behavior guidance, decides the authorization level, delegates to isolated worker/validation agents when allowed, and returns a concise cognitive receipt.
---

# Codex Task Orchestrator

Use this skill when the user wants to hand a task document to a principal agent instead of personally building the plan and supervising every execution detail.

This skill defines workflow. It does not define the user's judgment style; load `principal-agent-behavior.md` for that. It does not define project facts; load the project-specific behavior document only when the task points to one.

## Inputs

Expected inputs:

- A task document path, usually created from a repo template.
- A principal behavior document path. Use `/inspire/hdd/global_user/chenyiming-240108120067/project/PersonalAgent/principal-agent-behavior.md` by default unless the user provides a different path.
- Optional project behavior document path.
- Optional authorization level.

If no task document exists, first help the user draft one from the task template. Do not start implementation from an informal request unless the user explicitly asks for a small direct change.

## Required Reading

Before running the workflow:

1. Read the task document.
2. Read the principal behavior document. Default path: `/inspire/hdd/global_user/chenyiming-240108120067/project/PersonalAgent/principal-agent-behavior.md`.
3. If the task document names a project behavior document, read it.
4. Read only the project files needed to confirm the active path.

Keep the principal document and project document conceptually separate:

- Principal document: how to judge.
- Skill: how to execute the workflow.
- Project document: project-specific facts and preferences.
- Task document: what this task is.

## Authorization Levels

Use the task document's level when provided. If missing, propose one.

- `L0 read_only`: diagnose and explain only.
- `L1 plan_only`: create or revise the plan only.
- `L2 plan_scoped_implementation`: implement after the plan is accepted; run targeted checks.
- `L3 closed_loop_execution`: implement, debug within scope, rerun validation, and produce a receipt.
- `L4 delegated_domain_task`: run the full principal-agent workflow for stable task families.

If the user's latest message conflicts with the task document, the latest message wins.

## Workflow

### 1. Normalize the task contract

Extract and restate:

- Goal.
- Non-goals.
- Allowed files or modules.
- Forbidden changes.
- Public interface, data/config, persistence, external system, or real-device constraints.
- Required evidence.
- Stop conditions.

Ask the user only for blocking decisions. Do not ask for implementation details that can be discovered locally.

### 2. Decide whether to delegate

Use subagents only when the user or task document explicitly permits multi-agent delegation. If delegation is not permitted, perform the same roles locally and state that no subagents were spawned.

Delegate when it materially helps:

- Executor agent: plan and/or implementation.
- Validation agent: independent review, tests, negative checks.
- Receipt agent: cognitive receipt when the result is complex.

Do not delegate the immediate blocking task if the main rollout must do it to keep progress moving.

### 3. Enforce isolated worktrees

Any code-writing subagent must work in an isolated worktree, forked workspace, or equivalent isolated environment.

When assigning a worker:

- State that it is not alone in the codebase.
- Give it a clear write set.
- Tell any code-writing worker to read and follow `/inspire/hdd/global_user/chenyiming-240108120067/.codex/skills/engineering-guardrails/SKILL.md` before editing.
- Tell it not to revert, reset, or overwrite edits by others.
- Tell it to report changed files, validation commands, and residual risk.

If isolation cannot be guaranteed, reduce the authorization level or ask the user before proceeding.

### 4. Plan phase

For tasks at `L1` or above, ensure there is a plan unless the task is explicitly small and direct.

The plan must include:

- Current behavior and active path.
- Target behavior.
- Non-goals.
- Implementation boundary.
- Files or modules to change.
- Files or modules not to change.
- Validation plan.
- Stop conditions.

The principal agent reviews the plan against `principal-agent-behavior.md`. If the plan is too broad, lacks evidence, or places semantics in the wrong layer, return it for revision.

### 5. Implementation phase

Proceed only when:

- Authorization allows implementation.
- The plan is accepted.
- Write boundaries are clear.

Implementation rules:

- Code-writing agents must follow the `engineering-guardrails` skill: lock the goal and acceptance condition, surface important assumptions, choose the smallest viable change, keep edits surgical, validate the changed path, and report residual risk.
- Stay plan-scoped.
- Prefer minimal changes.
- Do not introduce fallback behavior unless explicitly justified.
- Do not change public contracts unless the task authorizes it.
- Preserve unrelated user or agent edits.

### 6. Validation phase

Validation must be independent from implementation when delegation is allowed.

Validation should check:

- The active path is covered.
- The changed behavior is exercised.
- Negative or boundary cases when practical.
- Environment/worktree correctness.
- Final integrated workspace, not only isolated worker state.

If validation cannot run, explain exactly why and what evidence remains missing.

### 7. Integration phase

The principal agent reviews worker diffs before integrating:

- Scope matches task and plan.
- No unrelated changes.
- No conflict with other worktrees or user edits.
- Validation evidence is sufficient.

After integration, run the necessary final checks in the main workspace.

### 8. Cognitive receipt

For `L3` or `L4`, produce or request a cognitive receipt.

Receipt structure:

1. What the task solved.
2. Final design in simple terms.
3. Key files/modules changed.
4. Minimal example, command, or usage path.
5. Validation evidence.
6. What was not verified.
7. Where to debug first if it breaks later.

## Stop Conditions

Stop and ask the user, or downgrade to read-only/plan-only, when:

- The user says read-only, do not modify, or explain only.
- Active path is uncertain.
- Plan conflicts with code facts.
- A public contract, data/config semantics, persistence format, external protocol, or real-device behavior must change unexpectedly.
- Worker isolation is unavailable for code-writing subagents.
- Validation cannot support the requested completion claim.
- Repeated fixes start relying on guesses.
- Unowned changes affect the same files.
- The user corrects the design theory or acceptance standard.

## Final Response

Report:

- Completion status.
- Changed files or documents.
- Validation evidence.
- Receipt path or concise receipt summary.
- Residual risk.
- Whether further delegation is safe.

Keep the final response concise. Do not paste raw subagent transcripts unless the user asks.
