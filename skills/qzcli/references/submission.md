# GPU、HPC 与批量任务提交

仅在用户请求准备、预览或实际提交任务时读取。以下命令里的名称、ID、镜像和路径必须用实际查询或用户给定的值替换。

## 选择资源和运行环境

确定 workspace、project、compute group、spec、镜像、容器启动命令、节点数、共享内存、优先级；数据集挂载仅在任务需要时添加。

- 名称解析可能模糊匹配到第一个资源，正式提交使用已核对的完整 ID。项目/组属于目标工作空间，spec 属于所选计算组。
- `--instances` 为实例/节点数；总卡数为 instances × spec 的每实例 GPU 数。核对 CPU、内存、卡型以及共享内存需求。
- CLI `create` 的镜像解析为显式值优先，再查平台/历史，失败则报错；不再依赖旧作者镜像。优先传入本机 `local_env.sh` 的镜像及来源，核对 `SOURCE_PRIVATE` / `SOURCE_PUBLIC`；批量和 MCP 仍有旧默认值，见下文。
- 默认共享内存仍为 1200 GiB，须按实际节点内存与任务需求显式设置；示例中的 64 GiB 不是固定规则。
- CLI `create` 优先级顺序为显式 `--priority` → 进程 `QZCLI_DEFAULT_PRIORITY` → 凭据 env 文件中的同名值 → `config.json.default_priority` → **4**。旧版兜底为 10。用户明确指定优先级时必须显式传入；不要自动把用户已有优先级改为 4，也不要为抢卡自行提高优先级。
- 数字越大优先级越高，训练与 HPC 同向；旧 help 中「训练 10 是低优」是错误描述。实际可用值还受工作空间/规格限制，不能保证每个空间接受 1–10 全部值。若被规格拒绝，CLI 会记录 (空间, 规格, 优先级)，再次提交前拦截并建议调整；`--force-priority` 仅跳过已知拒绝记录，不绕过平台限制。不要不经判断地强制或重试原组合。
- 启动命令在容器中执行；CLI 不自动上传当前目录。确认代码/数据/输出路径可在任务容器挂载或镜像中访问。`--instances > 1` 不会自动将单机脚本改为分布式训练，核对脚本的 rank、master、进程数等启动约定。
- 可读取用户指定的启动脚本或历史任务详情来复用镜像、资源和命令，但不要复用旧 job ID，也不要从无关任务推断用户意图。

## 获取规格

`qzcli res -w "工作空间"` 展示现有缓存。quick 刷新后 specs 可能仍为空：

1. 用户在终端交互操作可用 `qzcli create -i -w "工作空间" --dry-run`，按需获取实时规格。
2. 自动化优先复用已核验的 spec ID；`create --spec <UUID> --dry-run` 会尝试补齐规格详情。模型不要启动全屏 TUI 后等待无人操作。
3. 缺规格时可用工具自身解释器调用 `get_api().list_specs(compute_group_id, workspace_id)`：当前优先读取 `GetScheduleConfig.predef_train_spec`，不可用再尝试旧 OpenAPI 和该工作空间任务历史。预定义规格接口可能无权限；不能把失败当成该组没有规格。按用户需要选择每节点卡数和 CPU/内存，不直接接受自动选择的第一项/最小 GPU 规格。
4. 必要时 `qzcli res -w "工作空间" -u --full`，扫描该空间历史任务，可能耗时很长且无历史任务时仍无规格。限定空间并保持进度反馈。无法确定实际规格时询问资源选择，不能猜 UUID。

规格可能属于多个组，核对平台的 `logic_compute_group_ids`，并确认 payload 卡型来自目标组；不能因 quota ID 相同就复用另一组的 GPU 型号。

## GPU 创建

```bash
qzcli create \
  --name "实际任务名" \
  --workspace "ws-实际ID" \
  --project "project-实际ID" \
  --compute-group "lcg-实际ID" \
  --spec "实际规格UUID" \
  --image "实际镜像地址:标签" \
  --image-type SOURCE_PRIVATE \
  --instances 1 \
  --shm 64 \
  --priority 4 \
  --framework pytorch \
  --command 'cd /实际容器内目录 && bash train.sh' \
  --dry-run
```

检查 payload 中 `workspace_id`、`project_id`、`logic_compute_group_id` 和 `framework_config`，尤其 `cpu` / `mem_gi` / `gpu_count` / `instance_count` / `shm_gi` / `resource_spec_price` / 镜像及完整命令。

dry-run 不创建任务，但可能查询接口和更新缓存；它允许规格不完整时输出 payload，退出码 0 不代表可以提交。若有规格缺失警告或 CPU/内存为 0，先补齐；GPU 任务的 GPU 数须符合需求。确认完整后，在授权范围内移除 `--dry-run` 执行一次。

公共数据集可多次加 `--dataset 'dataset_id:version_id'`，省略版本默认 `v1`。此选项不等同于任意宿主机目录挂载。若镜像不是私有来源，查询实际支持的 image type，不能猜枚举。

本版本 CLI 的 `--json` 输出前仍可能夹杂展示文本，不能对整个 stdout 直接 `json.loads`。优先利用 MCP 结构化结果，或明确提取最后 JSON 块/返回的 Job ID。需要自动化执行带复杂引号的命令时用 Python `subprocess.run([...])` 参数数组。

提交后 `qzcli status <job-id>`。GPU 链接格式：`https://qz.sii.edu.cn/jobs/distributedTrainingDetail/<job-id>?spaceId=<workspace-id>`。

## 平台自动容错和节点约束

用户要求失败自动重跑时，在完整 `create` 命令上添加：

```bash
--auto-fault-tolerance --fault-tolerance-max-retry 3 --fault-tolerance-retry-interval-sec 300
```

上面仅为参数片段，重试次数和间隔按任务确定。自动容错默认关闭；两个数值均须非负且必须同时开开关，省略数值则用平台默认。检查 dry-run 顶层 `auto_fault_tolerance`、`fault_tolerance_max_retry`、`fault_tolerance_retry_interval_sec`。

平台会重跑同一条启动命令，不会自动替脚本实现 checkpoint 恢复。核对重复执行时的恢复/输出行为；已交给平台重试的任务应查询同一 job ID，不另起客户端重提循环。提交响应不明时的去重规则仍然适用。

`--exclude-node <节点名>` / `--include-node <节点名>` 可重复，分别进入 `exclude_nodes` / `specified_nodes`。排除依据来自实时资源或节点诊断；绑定节点还要求空间启用该能力，`specified_nodes not enable` 不能靠重试修复。不要为排队任务自行取消重建。

## 批量任务

`batch` 读取 JSON 的 `defaults`、非空 `matrix`、`name_template`、`command_template`；matrix 做笛卡尔积。先明确组合数、每任务资源和潜在总占用，不自动增加用户未请求的实验维度。

```json
{
  "defaults": {
    "workspace": "ws-实际ID",
    "project": "project-实际ID",
    "compute_group": "lcg-实际ID",
    "spec": "实际规格UUID",
    "image": "实际镜像:标签",
    "image_type": "SOURCE_PRIVATE",
    "instances": 1,
    "shm": 64,
    "priority": 4
  },
  "matrix": {"seed": [1, 2]},
  "name_template": "train-seed-{seed}",
  "command_template": "bash /实际路径/train.sh --seed {seed}"
}
```

```bash
qzcli batch batch.json --dry-run
qzcli batch batch.json --delay 3
```

`batch --dry-run` 现在逐项调用 `cmd_create(dry_run=True)`，会解析资源并输出 payload。**当前 dry-run 分支最终仍返回 0，即使某项预检失败或提前终止**；检查每项结果与实际覆盖数量，不能只看总退出码或「预览完成」文案。

`batch` 缺省优先级仍为 **10**，缺省镜像仍是旧作者镜像，未继承单任务 `create` 的新默认解析；在 `defaults` 中显式填写优先级、镜像和 image_type。`defaults` 字段不会按 matrix 自动模板化，混合资源配置需分批或逐个 `create`。

当前源码 `cmd_batch` 在遍历 `variables.items()` 时为含 `/` 的字符串 matrix 值增加 `_basename` 字段，会修改正在遍历的字典。使用路径作为 matrix 值前检查是否已修复；未修复时避免该路径，使用数值/短标识 matrix 并把路径放入 command_template，或用参数数组逐个调用 `create`。不要以真实提交试探这个问题。

当前 `batch` 未转发 `dataset`、节点包含/排除、自动容错三参数及 `force_priority`；把它们写进 JSON 不会生效。需要这些功能时用参数数组逐个 `create` 并分别检查 payload。失败后保留已成功 ID，默认在创建失败处停止；只有用户需要时才用 `--continue-on-error`，不重跑整批制造重复任务。

## HPC / CPU（Slurm）

```bash
qzcli hpc \
  --name "实际HPC任务名" \
  --workspace "ws-实际ID" \
  --project "project-实际ID" \
  --compute-group "lcg-实际ID" \
  --predef-quota-id "实际配额UUID" \
  --cpu 8 --mem-gi 32 --instances 1 \
  --cpus-per-task 8 --memory-per-cpu 4G \
  --priority 1 \
  --image "实际HPC镜像:标签" \
  --entrypoint 'cd /实际容器内目录 && bash run.sh'
```

上面 CPU/内存值仅为示例，必须与实际配额匹配，Slurm 每任务/每 CPU 参数也须与节点资源相容。需要 Cookie；`--compute-group` 使用完整 lcg ID，`--predef-quota-id` 为真实资源配额 ID。

HPC `--priority` 默认 1，数值越大越高；`--cpus-per-task` 实际默认 1，不是 help 声称的「同 --cpu」，故按任务显式传值。

当前 `hpc` 无 `--dry-run`。预览时生成命令和资源摘要即可，不执行；明确要求提交时再执行。HPC 链接为 `https://qz.sii.edu.cn/jobs/hpc?spaceId=<workspace-id>`。`status` / `logs` / `stop` 调用训练任务接口，不能据此假定支持 HPC；先检查当前版本 HPC 查询/管理接口，或报告需在 HPC 页面核实。`qzcli hpc-usage --help` 可查看节点使用率查询参数。
