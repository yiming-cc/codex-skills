---
name: restore-vrdma
description: Restore and verify the pinned Tencent TI-ONE vRDMA userspace stack after apt operations replace or break rdma-core, ibverbs, libfabric, libvrdma, or the NCCL OFI plugin. Use for Taco/Pro5000 training images when libvrdma.so is missing, NCCL falls back to Socket, RDMA packages were upgraded to Ubuntu t64/newer versions, or the image must be repaired before a multi-node NCCL test.
---

# Restore vRDMA

Use the bundled script as the single recovery entry point. Resolve `scripts/restore_vrdma.sh` relative to this `SKILL.md`, not relative to the current project directory. It downloads and verifies the pinned Tencent vRDMA bundle, resolves apt prerequisites, reinstalls the vRDMA packages, removes the incompatible `irdma` provider entry, rebuilds `aws-ofi-nccl` at `v1.7.3-aws`, and validates the critical packages and shared libraries. It deliberately omits the bundle's Python 3.10-only `python3-pyverbs` package on the Python 3.12 base image; that package is not part of the NCCL transport path.

## Workflow

1. Run a read-only inspection when diagnosing the current image:

   ```bash
   bash scripts/restore_vrdma.sh --verify-only
   ```

2. Explain that recovery changes system packages and requires root. Then run:

   ```bash
   bash scripts/restore_vrdma.sh
   ```

3. Report the saved package manifest, final package versions, and `ldd` results printed by the script.

4. Treat library verification as necessary but not sufficient. Confirm actual transport with a root, multi-node NCCL smoke test; require logs containing `Selected Provider is vrdma`, `NET/IB`, and `Using network vrdma-v6`, with no `NET/Socket` fallback.

## Guardrails

- Do not run a standalone `apt --fix-broken install` and save the image afterward. Finish all apt work first, then make this recovery the final system-library operation.
- Do not substitute Ubuntu repository RDMA packages for the pinned Tencent bundle.
- Do not persist NCCL runtime environment variables in the image as part of recovery; supply them in the training launcher.
- Do not claim RDMA is operational from file presence alone. Only a multi-node NCCL run proves the data path.
- If the script fails after apt changes, inspect its recovery attempt before running more package-manager commands.

## Overrides

Use environment variables only when deliberately changing the working or backup location:

```bash
WORKDIR=/var/tmp/restore-vrdma \
BACKUP_DIR=/var/tmp/restore-vrdma-backup \
bash scripts/restore_vrdma.sh
```
