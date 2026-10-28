# 排队、节点、资源与接口诊断

仅在用户请求诊断、看板或需要解释资源/运行状态时读取。根据问题选择下面的路径，不必每次跑完整诊断。

## 任务日志和排队事件

```bash
qzcli logs job-实际ID --since 10m --tail 100 --raw
qzcli events job-实际ID --tail 30
qzcli events job-实际ID --all-instances --type Warning --tail 30
qzcli events "开发机名称或notebook URL" --tail 30
```

- 日志默认通过 `ListJobInstances` 获取真实实例名，可能带轮次后缀，例如 `-worker-0-0`。只有查询到真实名称后才指定 `--pod`；不要从 job ID 拼接。失败时区分实例名错误、认证、平台日志超时和空日志。
- `status` 在等待态会尝试附带排队原因；需要完整证据时用 `events`。`--all-instances` 为训练任务追加 Pod 级事件；开发机走 `ListNotebookEvents`，不要认为所有训练过滤参数都同样适用。
- 开发机诊断只看最近启动轮次；训练事件需结合时间与当前状态，旧轮次失败不能证明当前仍失败。过滤后无事件表示无匹配记录，不等于资源充足。
- 资源不足、计算组/亲和性不匹配、抢占、拉镜像失败的解决方式不同。报告最近事件原意及证据，不能仅凭空闲卡数猜排队原因；查询或诊断不授权自动取消重提、抢占他人任务。

## 节点健康

```bash
qzcli events --node "节点名A" --node "节点名B"
```

节点名从实际任务实例/资源结果取，不能把 job ID 当节点名。该路径查 `cluster ListNodeEvents`，按节点查询最新记录；与任务自己的事件不同。

区分 GPU XID、GPFS 挂载、NotReady、磁盘/内存压力、禁止调度，以及后续恢复事件。新版 CLI 将超过 7 天的未恢复记录降为历史信息；这只是诊断时效规则，不能据此保证硬件健康。只结合近期证据建议 `--exclude-node`，不要因历史出现过 Unhealthy 就永久排除，也不要把没有事件解释成已验证正常。

## 占卡、碎片与看板

`avail` 回答资源分配情况；显示的「GPU利用率」实际是分配率。真实运行利用率来自平台 `gpu.usage_rate`，dashboard 用该字段，不能拿占卡比例判断任务空转或回收风险。

```bash
qzcli avail -w "实际工作空间" -v
qzcli dashboard -w "实际工作空间" --port 8520 --no-browser
```

- verbose 可列出碎卡节点及排除参数建议；按用户需要判断是否排除，排除可能缩小候选池。`--lp` 的可回收卡数仍不是真正空闲量。
- dashboard 可按计算组、优先级、项目、用户、任务下钻，查看真实利用率、运行时长和整节点容量。空闲容量会排除禁止调度节点；不要把不同视图和共享物理池直接相加。单纯数量查询用 avail，无需启动常驻看板。
- 看板为持续运行的 Streamlit 进程；用户要求启动时保留进程标识并报告端口/实际可访问地址。`--no-browser` 只关闭自动开浏览器，不代表配置了访问隧道。
- 依赖为可选 extra：streamlit / plotly / pandas。缺失时说明缺项；只有任务包含安装/环境变更时才用工具自己的环境安装，不在训练项目环境隐式加包。

## 认证、缓存和网络

- 找不到 workspace/project/group：核对精确名称/完整 ID，必要时限定空间 quick 刷新。缓存为空或缺字段属于未知，不能据此断言资源不属于该空间；查询失败不等于无资源。新版刷新会阻止空结果覆盖非空组/项目缓存，出现保护提示先处理认证/接口错误。
- 缺规格：按 [submission.md](submission.md) 获取目标组规格，重复 quick 刷新不会补出 specs。
- Cookie 过期：复用自动续期；凭据错误/锁号按 SKILL.md 处理，必要时 `qzcli ops --op login --since 2` 查时间线，不能循环删除封锁或重复登录。
- 代理来源是 `config.json.proxy` → `ALL_PROXY` → `HTTPS_PROXY`；传入目标 URL 的请求会遵守 `NO_PROXY` / `no_proxy`，包括配置文件中的代理。不能因只设 `HTTP_PROXY` 就断言 qzcli 会使用它；结合具体请求路径核验。只汇报配置是否存在和脱敏错误。

## API 版本与过时文案

v0.4.15 已迁移多条主路径到 v2，包括项目列表 `project GetProjectForPage`、开发机访问地址 `notebook GetNotebookAccessUrl`。底层仍有兼容 fallback；不能概括成「完全没有 v1」或沿用 README 的「这两条只能走 v1」。

`GetScheduleConfig.predef_train_spec` 是规格来源之一，仍可能权限不足；不能据旧 docstring 断言 v2 永远拿不到规格 ID。不同服务的同名 Action 不保证同权限，普通资源查询优先使用 qzcli 封装，不把 `cluster.*` 与 `workspace.*` 互换。`events --node` 是当前已实现的 cluster 端点例外。

判断平台是否有某能力时，以当前实现和实际接口响应为准。仓库 `docs/api_spec_v2.json` 及官方工具的 spec 都不保证覆盖全部 Web 接口；不因检索不到就宣布平台不支持。保留相关原始字段并脱敏，不回显完整响应或私有日志。
