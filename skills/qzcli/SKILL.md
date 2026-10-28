---
name: qzcli
description: "操作启智平台（qz.sii.edu.cn / Inspire）的 qzcli：查询 GPU 与整节点资源、提交和管理训练/HPC 任务、诊断排队与节点故障、远程执行及开发机持久化。用户请求启智平台操作或维护 qzcli 时使用。"
---

# 启智平台 qzcli

根据用户请求执行平台操作，默认用中文汇报。CLI 是本环境已安装、可独立使用的入口；若当前会话已暴露 qzcli MCP 工具，可优先用其结构化查询结果。不要假设 MCP 已注册，也不要为了完成普通 CLI 请求先安装 MCP。

本技能按 qzcli **v0.4.15 / `1e64bb1`** 核验。先用 `qzcli --version` 确认当前版本；用法冲突时核对当前 parser 和执行代码。上游 README、docstring 及部分 help 仍有旧描述，不能仅凭文案判断功能是否存在。

## 当前环境与认证

- 提交或生成命令前，若存在 [references/local_env.sh](references/local_env.sh)，先读取并加载其中的本机非敏感默认值。它记录本 Codex 安装的默认 workspace、project、image 等；用户本次显式选择始终覆盖这些默认值。该文件由 Codex 加载并展开为 CLI 参数；与 qzcli 原生消费的 `QZCLI_HOME`、`QZCLI_SESSION_ID`、`QZCLI_DEFAULT_PRIORITY` 不同。
- 项目：`/inspire/hdd/global_user/chenyiming-240108120067/project/qzcli_tool`。
- CLI：优先 `command -v qzcli`；当前绝对路径为 `/inspire/hdd/global_user/chenyiming-240108120067/conda/anaconda3/bin/qzcli`。换机器时重新发现路径。
- 持久化配置：`/inspire/hdd/global_user/chenyiming-240108120067/.qzcli/`，通过 `~/.qzcli` 软链接访问。当前进程的 home 为 `/root`。
- 已设置 `QZCLI_HOME` 时，以该目录为准：配置、Cookie、资源缓存、任务记录和登录锁均随之切换，须在进程启动前设置。不要为了普通查询新建状态副本；保持当前认证上下文。
- `.env` 中配置 `QZCLI_USERNAME`、`QZCLI_PASSWORD`；`.bashrc` 设置 `QZCLI_ENV_FILE` 指向上述 `.env`。Cookie、缓存和任务记录也在该目录。非交互 shell 可直接依赖软链接，或仅显式设置 `QZCLI_ENV_FILE`，无需 source 整份 `.bashrc`。
- 用户已自行配置账号。先复用 Cookie 做请求；失效时使用已有凭据刷新。认证读取优先级为 CLI 参数、密码 stdin、进程环境变量、指定/默认 `.env`、`config.json`、交互输入。
- 不打印或复制密码、Cookie、认证文件内容到回复、技能、脚本或日志。诊断只报告凭据是否存在。不要让用户把密码发到聊天中。
- 需要重登时，`qzcli login` 会打印 Cookie 前缀：将输出捕获到内存，只汇报成功或脱敏错误。一次明确的认证失败后不要反复尝试相同凭据；让用户检查本地配置。`login` 走 CAS/Cookie，避免以 `init` 的旧 Token 流程替代。
- 新版在并发查询前统一鉴权，worker 不会自行重登；错误凭据/锁号会封锁后续自动重登，等待不会清除本地封锁。修正凭据或平台限制解除后，成功的手动 `qzcli login` 才会清除它；不要删除锁/冷却文件或循环 login 绕过保护。

## 查询剩余资源

```bash
qzcli res --list
qzcli res -u                           # 首次无缓存/资源变更时使用
qzcli avail                            # 用户未限定空间时查询全部
qzcli avail -w "工作空间名称" -v         # 指定空间，含空闲节点名
qzcli avail -w "工作空间名称" -n 4       # 找满足 4 节点的组
qzcli res -w "工作空间名称"             # 查看缓存的项目、计算组、规格
```

- 查询实时可用量用 `avail`，不能把 `resources.json` 或交互快照当实时余量。缓存有效时不必每次全量刷新。
- `res -u` 默认 quick，只刷新工作空间/项目/计算组，不刷新 specs。缺规格时见 [任务提交](references/submission.md)，不要反复 quick 刷新期待规格出现。
- 按型号需求筛选实际 GPU/NPU 类型字段；未知型号不要凭名称猜成目标型号。
- 区分 **空闲 GPU 总数**、**完全空闲节点**、**每节点卡数**。用户要求整台 8 卡时核对节点规格和整节点空闲，不能用碎片空卡总数除以 8。
- `avail` 表头虽叫「GPU利用率」，数值是 `(总卡 − 空闲卡) / 总卡` 的分配率；不能据此判断 GPU 是否空转或会被空闲回收。真实利用率、碎片和看板见 [references/diagnostics.md](references/diagnostics.md)。
- `--lp` 仅在用户考虑低优任务资源时使用，表示潜在可回收资源，不是当前真正空闲资源；查询较慢，应尽量限定工作空间。查询本身不授权停止或抢占任务。
- 多个逻辑计算组可能共享物理资源池。保留分组口径；只有拿到物理组/节点身份并去重后才能汇总跨组总容量。
- 选择训练计算组时，先按用户要求的卡型和每任务节点形状检查实时 `avail`，优先使用当前拥有足够完整空闲节点的池；多个池都满足时，优先完整空闲节点更多的池，再参考空闲 GPU 数。用户显式指定计算组时不自动改组。
- 如果没有任何池被实时确认能满足本次完整节点需求，或实时余量接口失败而无法确认，使用 `references/local_env.sh` 中的 `QZCLI_FALLBACK_*_COMPUTE_GROUP_*`。当前本机 H100 回退池为“开发区-H100-cuda13.2版本-183核”；回退不代表已确认有空卡，提交后仍须如实报告排队状态。切换计算组后重新核验该组可用的 spec，不能盲用另一组的 spec ID。
- 空闲量是查询时快照，不保证用户的项目配额、权限、镜像或调度策略允许立即开跑。部分接口失败应标明缺失范围，不能把失败当成 0。
- `avail -e` 是人类可读的导出混合输出，不用 `eval` 执行；其中自动推荐的规格也需核验。

汇报查询时间（注明时区）和范围，用表格列出工作空间、计算组、卡型、空节点、空 GPU，按需给出适合用户需求的候选。不固定记忆实时数字或私有资源 ID。

## 任务提交与权限边界

提交 GPU、HPC 或批量任务时读取 [references/submission.md](references/submission.md)。

- “看看资源”“如何提交”“生成命令”“预览”不代表实际创建任务。
- 用户明确要求提交/停止/执行，且目标和必要参数已确定时，直接完成授权操作；已有授权在本任务内持续有效，不重复索取确认。
- 若关键参数缺失且不能从用户指定脚本、历史任务或本次上下文可靠推断，先完成资源查询和可生成的命令/配置，再只询问影响执行的缺失信息。不要把作者默认镜像或缓存第一项当作用户选择。
- 用户未指定 project、workspace 或 image 时，优先使用 `references/local_env.sh` 中对应的 `QZCLI_DEFAULT_*`；不存在或为空时再从缓存、历史任务或用户输入确定。不要把这些本机默认值写成跨机器通用规则。
- 在 LogosVLA 仓库提交实验时，启动命令默认直接使用用户指定的主工作区源码，不主动复制、构建或切换到 `source_snapshots`。用户负责保证任务排队和运行期间相关代码逻辑稳定；只有用户明确要求源码快照时才创建。
- 若本机默认 `QZCLI_DEFAULT_TRAINING_LAUNCH_MODE=direct-formal`，不要自行在正式训练前增加 3-step smoke；只有用户明确要求，或已确认的实验计划把 smoke 定义为必要依赖时才提交 smoke。该默认值不跳过 dry-run payload 检查、本地配置检查或正式任务启动后的日志验收。
- GPU 提交前生成并检查 `create --dry-run` 的实际 payload；这是内部验证，不是额外审批。用户只要预览时到此结束。
- 创建请求超时/断连且结果不明时，先按任务名、工作空间、创建时间查询是否已创建；没有唯一判断前不要再次提交。批量只重试确定未创建的条目。
- 提交成功必须取得 job ID，并查询状态；区分已受理/排队/运行/完成。状态暂时查询失败时保留成功 ID，报告状态未知，不重提。

## 状态、日志与开发机

```bash
qzcli ls -c -w "工作空间名称" -r
qzcli ls -c --all-ws -r
qzcli status job-xxx
qzcli logs job-xxx --tail 100 --raw
qzcli events job-xxx --tail 30
qzcli stop job-xxx --yes                 # 仅在用户明确授权停止此任务后
```

`ls -c` 查询平台；不加 `-c` 主要看本地追踪记录。`remove` / `clear` 删除的是本地记录，不会停止平台任务。日志默认做有界查询，只有用户要求持续监控时使用 `--follow` 或 `watch`。上面的状态/日志/停止流程针对 GPU 训练任务，HPC 支持另见提交参考。

- 排队/抢占、节点健康、日志实例选择、GPU 看板：读 [references/diagnostics.md](references/diagnostics.md)。日志默认让 CLI 查询平台真实实例名，不自行拼 `--pod`。
- 开发机 exec、训练 worker exec/diag、devbox 持久化、操作日志、MCP 差异或上游版本维护：读 [references/advanced.md](references/advanced.md)。
- 未知平台状态保留原始值，不把未知枚举自动判为失败；MCP 可用时用 `qz_inspect_status_catalog` 核对。

## 完成后的反馈

查询返回实时结果和必要限制；提交返回任务名、job ID、工作空间、计算组、资源数量、当前状态和平台链接；停止返回确认结果。执行失败说明具体阶段及下一步，不宣称成功。凭据、私有日志和命令中的敏感值不在回复中回显。
