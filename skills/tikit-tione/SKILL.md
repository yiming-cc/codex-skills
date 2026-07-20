---
name: tikit-tione
description: Work with Tencent Cloud TI-ONE Tikit Python SDK. Use when Codex needs to generate, review, or run Python automation for TI-ONE resources including Client initialization, datasets, COS/HDFS/Hive data operations, training tasks, development machines/notebooks, model acceleration, online model services, batch tasks, logs, metrics, and Tikit environment inspection.
---

# Tikit TI-ONE

Use this skill to help users operate Tencent Cloud TI-ONE through the Tikit Python SDK. Prefer generating auditable Python scripts over ad hoc console instructions.

## Safety

- Never print, copy, or persist `SecretId`, `SecretKey`, tokens, cookies, or platform credentials.
- Prefer environment variables or platform-managed credentials over hard-coded keys.
- Treat delete, stop, overwrite, traffic-shift, and sync-with-delete operations as destructive; require explicit user intent.
- Treat Tikit as an image-level public control-plane tool. First discover the image-provided CLI, interpreter, and non-secret configuration; do not infer that Tikit is absent only because a project's virtual environment cannot import it.
- Keep Tikit control-plane processes separate from project runtimes. Do not install Tikit into a project's environment; repair or provide the image-level public Tikit runtime when it is missing or broken.

## Quick Start

Resolve the installed skill directory instead of hard-coding a host path:

```bash
TIONE_SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/tikit-tione"
```

Load image-level non-secret defaults and select the public control-plane interpreter:

```bash
if [ -f "$TIONE_SKILL_DIR/references/local_env.sh" ]; then
  set -a
  . "$TIONE_SKILL_DIR/references/local_env.sh"
  set +a
fi
TIONE_CONTROL_PYTHON="${TIONE_CONTROL_PYTHON:-/usr/bin/python3}"
```

Use that interpreter for Tikit helpers:

```bash
"$TIONE_CONTROL_PYTHON" "$TIONE_SKILL_DIR/scripts/tikit_helper.py" check
"$TIONE_CONTROL_PYTHON" "$TIONE_SKILL_DIR/scripts/tikit_helper.py" resources
"$TIONE_CONTROL_PYTHON" "$TIONE_SKILL_DIR/scripts/training_task.py" submit-smoke
"$TIONE_CONTROL_PYTHON" "$TIONE_SKILL_DIR/scripts/training_logs.py" <task-id>
"$TIONE_CONTROL_PYTHON" "$TIONE_SKILL_DIR/scripts/tikit_helper.py" methods training
```

`references/local_env.sh` may contain environment-specific non-secret values
such as region, resource group ID, VPC/subnet IDs, CFS mount ID, default GPU
type, runtime user, resource profiles, and verified custom image tuples. Never put secrets in that file. `training_task.py`
also reads it automatically for default CLI values, but source it when writing
raw shell commands or ad hoc scripts.

`tikit_helper.py check` inspects the current interpreter, configured control
interpreter, Tikit CLI shebang, and common image path. If none can import Tikit,
report an image/environment problem. Do not repair it by modifying an unrelated
project environment.

The command submitted to TI-ONE is a separate project process. Enter that
project's own runtime in the startup command using the project's documented
venv, uv, conda, container entrypoint, or equivalent. Do not assume the public
Tikit interpreter contains project dependencies, and do not assume the project
runtime contains Tikit.

If a task needs detailed API shape, read `references/tikit_notes.md` before writing code.

## Workflow

1. Identify the requested TI-ONE operation: data, training, development machine, model acceleration, online service, batch task, logs, metrics, or general inspection.
2. Run `scripts/tikit_helper.py check` with the image-provided control interpreter. If the current project interpreter lacks Tikit but an image-level candidate works, use the image-level candidate without changing the project environment.
3. For resource inspection, prefer `scripts/tikit_helper.py resources` and summarize only totals plus active resource names/statuses unless the user asks for detail.
   - Check GPU availability by **GPU type**, not only total GPU count. If one card type is saturated, consider another available card type instead of queueing everything on the first type.
4. For training task submission, prefer `scripts/training_task.py` instead of ad hoc Python. First load local defaults from `references/local_env.sh` if present. Always run a dry-run first without `--yes`; use `--plan-format json` for machine validation. Add `--yes` only after the user explicitly confirms the exact plan.
5. Generate a minimal script with `scripts/tikit_helper.py render <kind>` and edit placeholders instead of writing large SDK calls from memory.
6. If `tikit` is available, use `scripts/tikit_helper.py methods <pattern>` to discover exact method names on `tikit.client.Client`.
7. For live operations, print planned task names, region, resource group, network IDs, data mounts, COS output paths, resource configs, and startup commands before executing.
8. Treat `resources` output as capacity information, not as guaranteed schedulability. If quotas or instance counts are ambiguous, run a small smoke task or dry-run before launching large jobs.
9. After submission, immediately check task status and logs. Use `scripts/training_logs.py <task-id>` to get pod names and concise error lines. Do this before submitting many similar tasks.
10. Use `--receipt <path>` for live submissions. The helper writes the returned task ID atomically and reuses a matching receipt instead of creating a duplicate task.

## Common Patterns

Initialize the client without embedding credentials:

```python
import os
from tikit.client import Client

client = Client(
    os.environ.get("TENCENTCLOUD_SECRET_ID"),
    os.environ.get("TENCENTCLOUD_SECRET_KEY"),
    os.environ.get("TENCENTCLOUD_REGION"),
)
```

Use COS paths in the form expected by Tikit docs, usually:

```text
<bucket>/<cos-prefix>/
```

For raw COS operations outside Tikit, prefer the separate `tencent-coscli` skill if available.

Mount CFS explicitly when a task must access paths from a development machine or shared filesystem. A path that exists in the current shell is not automatically visible in a training task.

```bash
--input-cfs CFS_ID:/source/path/in/cfs:/mount/path/in/container
```

Common full-root mount shape:

```bash
--input-cfs cfs-xxxxxx:/:/cfs
```

Explicit `--input-*` arguments replace the corresponding image-level defaults.
The helper removes exact duplicates and rejects different sources that target
the same mount path. Use `--no-default-inputs` when a task should have no
image-level default mounts. Never clear environment variables in a project
wrapper merely to work around duplicate mounts.

To discover a CFS mount used by a running development machine, inspect notebook details:

```bash
"$TIONE_CONTROL_PYTHON" - <<'PY'
import os
from tikit.client import Client

client = Client(
    os.environ.get("TENCENTCLOUD_SECRET_ID"),
    os.environ.get("TENCENTCLOUD_SECRET_KEY"),
    os.environ.get("TENCENTCLOUD_REGION"),
)
print(client.describe_notebook("NOTEBOOK_ID"))
PY
```

Look for `DataConfigs`, `MappingPath`, and `CFSSource.Id`.

For custom images, record and verify the full image tuple before submission:

```text
image_url: registry-domain/namespace/repository:tag
image_type: TCR | CCR | CUSTOM
registry_region: ap-...
registry_id: tcr-...        # when using TCR
```

Do not assume `latest` exists or points at the intended build. Confirm the exact
tag in the registry console or with the available registry SDK/API, then use that
tag explicitly in `--image-url`. If a task fails with an image-not-found message,
recheck the namespace, repository name, tag, registry region, registry id, and
image type as one set.

Keep reusable skill notes generic. Concrete non-secret image defaults may live in
`references/local_env.sh` for this Codex installation; do not put image secrets,
registry passwords, or credential URLs there.

Runtime environment variables should be treated as part of the requested training
environment, not as automatic safety defaults. Do not add NCCL, RDMA, CUDA,
library path, proxy, cache, or framework environment variables unless one of
these is true:

- the user explicitly requested the variable or named an environment profile;
- the variable is already present in the user-provided startup command;
- a directly matching local reference profile exists for the requested hardware
  or cluster shape, such as `references/pro5000_multinode_env.sh` for pro5000
  multi-node training.

When applying a local reference profile, read the profile first, source it in the
startup command before the training command, and show the resulting environment
plan in the dry-run. Do not invent or carry over NCCL settings from previous
jobs.

For pro5000 multi-node training, use `references/pro5000_multinode_env.sh` as the
environment profile unless the user asks for different transport settings.

For multi-node training tasks, enable TI-ONE RDMA by default. In
`scripts/training_task.py`, this means `workers > 1` resolves to
`enable_rdma=True` unless the user explicitly passes `--no-enable-rdma`. Treat
this as a TI-ONE task option, not permission to add NCCL/RDMA environment
variables beyond the rules above.

Training tasks may execute the start command as `root` even when the CFS mount
belongs to a normal development user. Do not write long-running outputs to a
shared CFS path as root unless the user explicitly wants that. Before launching
real training, check the container user and write ownership:

```bash
id
stat -c '%u %g %n' /cfs/path/to/user-or-workdir
touch /cfs/path/to/workdir/.tione_owner_smoke
ls -l /cfs/path/to/workdir/.tione_owner_smoke
rm -f /cfs/path/to/workdir/.tione_owner_smoke
```

When `TIONE_DEFAULT_RUN_USER=root`, keep the task as root and do not apply the
user-switching pattern below. `training_task.py` shows `run_user: root` in the
dry-run and prepends a UID-0 fail-fast check to the submitted start command.
Expect CFS artifacts to be root-owned and repair ownership after training when
the user requires normal-user access. Use `--run-user image-default` only when a
specific task should opt out of this local root requirement.

If the command starts as root, switch to a user with the same UID/GID as the CFS
owner before running training. Some custom images already contain a user such as
`guchun` with the CFS owner's UID. Always check by UID first and reuse that user;
otherwise `useradd -u ...` can fail with `UID ... is not unique`. A robust pattern
is:

```bash
WORKDIR=/cfs/path/to/workdir
USER_HOME=/cfs/path/to/user_home
USER_ID="$(stat -c %u "$USER_HOME")"
GROUP_ID="$(stat -c %g "$USER_HOME")"
RUN_USER="$(getent passwd "$USER_ID" | cut -d: -f1 || true)"
if [ -z "$RUN_USER" ]; then
  getent group "$GROUP_ID" >/dev/null || groupadd -g "$GROUP_ID" cfsgrp
  RUN_USER=training_user
  useradd -u "$USER_ID" -g "$GROUP_ID" -d "$USER_HOME" -s /bin/bash "$RUN_USER"
fi
runuser -u "$RUN_USER" -- bash -lc "cd '$WORKDIR' && <training command>"
```

When `runuser` is unavailable, try `su -s /bin/bash "$RUN_USER" -c "..."`.
Avoid `su -` unless a login shell and that user's home/profile are known to be
correct inside the training container.

## Task Guidance

- **Datasets and data movement**: Use Tikit dataset APIs for TI-ONE datasets. Use helper/data snippets for COS, HDFS, and Hive skeletons; verify exact method names with `methods`.
- **Training tasks**: Use `scripts/training_task.py` for common starts:
  - `submit-smoke`: short no-op GPU task for platform validation.
  - `submit-system`: TI-ONE built-in framework image.
  - `submit-custom`: custom image.
  - `status <task-id>`: concise task status.
  - `wait <task-id> --until started|terminal`: wait through the shared TI-ONE state machine.
  - `scripts/training_logs.py <task-id>`: pod names plus filtered recent logs.
  Resource/network IDs are environment-specific. Prefer `references/local_env.sh` or setting `TIONE_RESOURCE_GROUP_ID`, `TIONE_VPC_ID`, and `TIONE_SUBNET_ID`; otherwise pass `--resource-group-id`, `--vpc-id`, and `--subnet-id` explicitly after checking `resources`.
  Custom image and runtime-user defaults can come from `TIONE_DEFAULT_IMAGE_URL`, `TIONE_DEFAULT_IMAGE_TYPE`, `TIONE_DEFAULT_REGISTRY_REGION`, `TIONE_DEFAULT_REGISTRY_ID`, and `TIONE_DEFAULT_RUN_USER` in `references/local_env.sh`; override them explicitly when a different image or runtime user is required.
  Resource profiles are examples only and may need overrides with `--gpu`, `--cpu`, and `--memory` based on the selected resource group.
  Minimal system submission parameters are `--name`, `--cmd`, and usually `--code-package-path`, `--cos-output`, plus data mounts such as `--input-cos bucket/path/:/mnt/data`.
  Do not assume a CFS path from the current shell is visible inside a training task. Mount it explicitly with `--input-cfs` or package/sync the code and data to COS.
  TI-ONE may require the `--cos-output` prefix to exist before task creation. If `InvalidParameterValue.CosPathNotExist` occurs, create the prefix with a small placeholder object using the `tencent-coscli` skill, then resubmit.
  Startup commands should be self-contained: `cd` to the mounted workdir, activate the required environment, and then run training. Avoid relying on interactive shell PATH changes that may only exist in the development machine.
  Prefer a one-GPU environment smoke task before launching many large tasks, especially when using a new image, CFS mount, or environment activation method.
  Treat `SUBMITTING`, `CREATING`, `PENDING`, and `RUNNING` as normal transient states; `SUCCEED` as success; and `FAILED`/`STOPPED` as terminal failures. Do not duplicate these status sets in project-specific watchers.
  A watcher failure after task creation is not proof that submission failed. Read the receipt and query the recorded task ID before attempting another submission.
  For dependent tasks, require the parent task to reach `SUCCEED` and pass its artifact audit before submitting children.
- **Development machines**: Tencent docs may still use `notebook` method names even though the product UI calls them development machines.
- **Model acceleration**: Confirm model source, framework/format, input tensor shape, output COS path, optimization level, and target GPU type.
- **Online services**: Treat version creation, service stop/delete, and traffic weight changes as user-visible production changes.
- **Batch tasks**: Confirm one-off vs periodic execution, input/output data source, image/model/code package, startup command, and resource config.

For large artifacts, do not treat file existence or platform success alone as
readiness. Require experiment-supplied size expectations, repeated stable size
checks, associated validation or manifest artifacts, save-log evidence, and
either post-save progress or a clean task exit.

## References

- `references/tikit_notes.md`: condensed notes from Tencent Cloud TI-ONE Tikit docs and links to official pages.
- `references/local_env.sh`: local non-secret TI-ONE defaults for this Codex installation; read it before task submission.
- `references/pro5000_multinode_env.sh`: local non-secret runtime environment profile for pro5000 multi-node training.
