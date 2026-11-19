---
name: aliyun-pai-dlc
description: "使用阿里云 PAI CLI 操作 PAI DLC 训练任务，包括查询配额与 GPU 余量、生成 dry-run、提交任务、查询状态、日志和事件。用户请求在当前 PAI DSW 环境启动或排查阿里云训练任务时使用。"
---

# 阿里云 PAI DLC

这个 Skill 面向当前 PAI DSW 环境中的官方 `pai` CLI。默认配置来自
[references/local_env.sh](references/local_env.sh)，其中只保存地域、工作空间、资源配额、镜像和非敏感资源默认值。

## 环境与认证

先解析 Skill 目录并执行检查：

```bash
ALIYUN_PAI_SKILL_DIR="${ALIYUN_PAI_SKILL_DIR:-$HOME/.agents/skills/aliyun-pai-dlc}"
python3 "$ALIYUN_PAI_SKILL_DIR/scripts/pai_dlc.py" check
```

当前 DSW 的持久化 setup 会将官方 PAI CLI 安装到
`/mnt/netdata/Team/Personal/ymc/.local/bin/pai`，并通过个人 `.bashrc` 设置
`PAI_CLI_BIN`、`PAI_CONFIG_DIR` 和 PATH。更换容器后先运行
`source /mnt/netdata/Team/Personal/ymc/setup`，再执行本 Skill。

脚本会自动读取 `references/local_env.sh`。AccessKey 不写入仓库，优先从当前进程的
`PAI_ACCESS_KEY_ID` / `PAI_ACCESS_KEY_SECRET` 或 `ALIBABA_CLOUD_ACCESS_KEY_ID` /
`ALIBABA_CLOUD_ACCESS_KEY_SECRET` 读取，也支持 `ALIYUN_PAI_CREDENTIAL_ENV_FILE`
指定的私密 env 文件，以及 `ALIYUN_PAI_CREDENTIAL_JSON_FILE` 指定的 owner-only JSON
文件。默认私密 env 文件位置是 `/mnt/netdata/Team/Personal/ymc/.config/aliyun-pai/accesskey.env`。
不要在输出、日志或回复中回显凭证。

当前 PAI CLI 的配置优先级是命令行、Profile、`PAI_*` 环境变量、
`ALIBABA_CLOUD_*` 环境变量。需要切换目标时显式传 `--region`、`--workspace-id`
或 `--resource-id`，不要修改共享默认值来临时切换账号。

## 工作流

1. `check` 确认 `pai` CLI、认证来源和目标范围。
2. `resources` 查询目标配额详情和 DLC 排队任务。配额返回中的 Total、Used、Submitted、Scheduled、Idle 等字段保持服务端原义，缺失字段不能当成 0。
3. `dry-run` 生成并检查完整请求体。它不会创建任务，也不代表库存、权限或镜像拉取已经通过。
4. 用户明确要求提交且计划已核对后，执行 `submit --live`。未传 `--live` 时 `submit` 自动使用 dry-run。
5. 提交后保存返回的 job ID，立即执行 `status` 和 `logs`。创建请求超时或结果不确定时，先用 `job list` 按名称和时间核对，不重复提交。
6. 调度问题先看 `events`，再看 `logs`。`Queuing`、`Dequeued`、`Running` 等中间状态不视为失败。

## 常用命令

```bash
python3 "$ALIYUN_PAI_SKILL_DIR/scripts/pai_dlc.py" resources

python3 "$ALIYUN_PAI_SKILL_DIR/scripts/pai_dlc.py" dry-run \
  --name <job-name> \
  --command "torchrun --nproc_per_node=1 train.py"

python3 "$ALIYUN_PAI_SKILL_DIR/scripts/pai_dlc.py" submit \
  --name <job-name> \
  --command "torchrun --nproc_per_node=1 train.py" \
  --live

python3 "$ALIYUN_PAI_SKILL_DIR/scripts/pai_dlc.py" status <job-id>
python3 "$ALIYUN_PAI_SKILL_DIR/scripts/pai_dlc.py" logs <job-id> --tail 200
python3 "$ALIYUN_PAI_SKILL_DIR/scripts/pai_dlc.py" events <job-id> --max 100
```

资源配额模式默认使用本地 env 中的 `resource_id`、CPU、内存和 GPU 数量。
按量 ECS 规格需要显式传 `--worker-spec`，并与 `--resource-id`、`--cpu`、
`--memory`、`--gpu`、`--gpu-type` 互斥。镜像默认使用 foundation-compute
登记的固定 tag。启动命令、任务名和数据挂载按任务显式指定。

详细参数和脆弱行为见 [references/configuration.md](references/configuration.md)。
资源查询和训练提交均通过官方 PAI CLI 完成，不直接导入 foundation-compute 的应用模块。
