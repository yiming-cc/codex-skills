# 远程执行、开发机持久化与 MCP

按需读取：开发机命令与 session、训练 worker、devbox、ops、MCP 能力差异。排队/节点事件和看板另见 [diagnostics.md](diagnostics.md)。

## 已有开发机远程命令

`qzcli exec` 使用 Jupyter terminal / contents API，不要求 SSH。目标可为开发机名、完整 notebook UUID、唯一 UUID 前缀或平台 IDE URL。这是使用已有开发机，不创建新的训练任务。

```bash
qzcli exec "开发机名称" nvidia-smi
qzcli exec --timeout 600 "开发机名称" bash /实际路径/script.sh
qzcli exec --detach "开发机名称" bash /实际路径/long_job.sh
qzcli exec-attach "开发机名称" qzcli_实际返回ID
```

`--timeout` / `--detach` 必须在 target 之前，后面的内容全部作为远端命令。默认本地等待 120 秒；本地超时不杀掉远端进程。长命令用 detach，保存 exec job ID 后 attach 轮询，避免因本地超时重复启动。

exec 的 `qzcli_...` ID 与平台训练 `job-...` ID 不同，不能混用管理命令。仅查询资源时不要在开发机上启动训练或安装依赖。

### 并发与续接

新版每次 exec 自建终端，不复用他人的交互终端；job ID 带 session、时间戳和随机段。session 来源：`QZCLI_SESSION_ID` → 凭据 env 文件 → `config.json.session_id` → 每进程自动生成。无需手动设置也能隔离并发；需要跨进程归为同一会话时再设置稳定的 session。

```bash
qzcli exec --list "开发机名称"
qzcli exec --list --all "开发机名称"
```

不固定 session 时，新 CLI 进程的 `--list` 默认看不到上一进程的任务；优先保存 job ID，遗失后用 `--all` 并核对目标。远端 `/tmp/.qzcli/<session>/` 不是持久存储，超过 7 天的 session 目录会在后续 launch 时被清理；重要输出由任务自身写持久盘。旧格式 job ID 仍可 attach。

v0.4.12 修复了首次 exec 的目录和终端就绪问题。仍超时时先检查版本、报错和已有输出，再 attach；不要把「无输出」当作未执行而重复启动，也不要为修复中转目录删除项目盘数据。

## 训练 worker 命令与通信诊断

`exec` 服务 notebook；训练容器使用独立的 WebSocket PTY 路径：

```bash
qzcli worker exec job-实际ID nvidia-smi
qzcli worker diag job-实际ID --index 0
```

- `worker exec` 没有开发机 exec 的 detach/attach 契约，不用于无人监管的长训练启动。远端命令含 `-` 开头参数时，核对 parser 或把完整命令作为一个字符串参数传入，避免被当成本地选项。
- 当前默认实例名仍拼成 `<job-id>-worker-<index>`，没有沿用 logs 的真实实例名解析。目标不匹配时通过 `get_api().list_job_instances(job_id)` 查询平台名称，再用 `--instance` 指定；不要照抄日志中旧命名约定。
- `worker diag` 检查 GPU、RDMA 状态/误码、到 master 的 TCP 和 NCCL 配置。它不能替代多节点 NCCL 带宽测试；计数器未暴露表示无法判断，历史累计误码也须结合时间增量，不能仅凭一项红色输出断定当前硬件损坏。回复不回显无关环境值。

## 开发机持久化

只有用户要求持久化或恢复开发机配置时使用 `devbox init`；普通诊断用 status。target 可为名称、notebook ID 或 URL，**省略 target 操作本机**。

```bash
qzcli devbox status "开发机名称"
qzcli devbox init "开发机名称" --only codex,bash_history --target-dir /实际账号持久目录 --dry-run
```

在已有授权范围内检查 dry-run 的路径和合并计划后，移除 `--dry-run` 执行。`--only` 限定用户需要的项，默认可能包含多种 agent 配置及历史。

- `/inspire/hdd/global_user` 父目录本身不保证持久，使用实际账号子目录；工具会验证文件系统与可写性。不要用自动探测覆盖用户明确给出的路径。
- 目录按并集合并，同名冲突保留较大文件并备份另一份；配置冲突以持久盘为准并备份本地文件。此策略不等同于语义合并，完成后检查冲突报告和实际链接。
- shell 历史通过 rc 中的 `HISTFILE` 定位，不靠软链。开发机重建后通常需要重跑 init 恢复链接，不宣称安装了永久启动钩子。
- `.ssh` 默认不托管；不要顺手加 `--include-ssh`。用户明确需要时核验目标权限。已有持久化链接先查状态，避免不必要的再次迁移。

## 操作日志

```bash
qzcli ops --since 24
qzcli ops --op login --since 2
```

`--since` 单位是小时。日志默认在当前 `QZCLI_HOME` 对应的状态目录，`--merge /另一状态目录` 可重复。主要记录提交、停止、登录、exec、资源刷新等操作；不完整记录只读查询，也不是平台状态或远端命令成功的证明。记录可能包含目标地址或 argv 片段，汇报前仍须脱敏；不要输出完整日志文件。

## MCP 可用时

只使用当前会话实际暴露的工具，调用前核对工具 schema。MCP 共享本地 Cookie 和缓存，不因文件里定义了工具就认为本会话能调用。

| 用途 | 工具及关键参数 |
| --- | --- |
| 现有凭据登录 | `qz_auth_login`，不传明文凭据参数 |
| 工作空间 | `qz_list_workspaces(refresh=True)` |
| 资源刷新 | `qz_refresh_resources(workspace=...)` |
| 剩余资源 | `qz_get_availability(workspace=..., group=..., required_nodes=..., include_low_priority=False)` |
| 任务列表/详情 | `qz_list_jobs` / `qz_get_job_detail` |
| GPU 创建 | `qz_create_job` |
| HPC 创建/用量 | `qz_create_hpc_job` / `qz_get_hpc_usage` |
| 停止 GPU 任务 | `qz_stop_job` |
| 工作空间用量 | `qz_get_usage` |
| 状态枚举核对 | `qz_inspect_status_catalog` |
| 开发机执行/续接 | `qz_exec` / `qz_exec_attach` |

版本限制：

- `qz_create_job` 无 dry_run、dataset、自动容错、节点包含/排除或 force_priority 参数；需要这些选项时走 CLI，尤其自动容错不能仅切换到 MCP 就保留。当前 MCP 默认优先级固定为 3；它不适用于用户要求 priority=4 的任务，此时必须使用 CLI 并显式传入 `--priority 4`。MCP 镜像仍有旧作者默认值，不使用 CLI 的完整镜像/default-priority 解析。
- `qz_create_hpc_job` 无 priority 参数，要求非默认 HPC 优先级时走 CLI。
- 当前 MCP 没有日志、events、worker、dashboard、devbox、ops 对应工具，使用 CLI，不能编造工具名。
- MCP 资源刷新实现可能扫描任务历史，不能当成 CLI `res -u` 的 quick 模式；普通快速刷新优先 CLI。
- `status_family` 是归一化判断，`status_raw` 和 `raw` 才是判断字段变化的依据。未知枚举先报告原值并核对，不能径自认定任务失败。

## 版本维护

维护上游仓库时先检查 git 状态、分支和 remote，记录旧 HEAD，再 `git pull --ff-only`；存在分叉或改动冲突时保留用户文件，不强制 reset。比较提交、实际代码与测试，不直接把 changelog 的历史结论当当前事实。

用已安装 CLI 自身的解释器在仓库外核验 `qzcli.__file__` / `__version__`，区分 editable 源码更新和需要重新安装的普通包；不要把控制工具装进训练项目环境。更新验证优先 help 和本地 mock 测试，使用临时 `QZCLI_HOME` 与空凭据文件；不要为验证提交、停止真实任务。普通查询不自动升级或重装工具。
