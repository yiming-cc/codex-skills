# 配置与参数说明

## 固定范围

当前默认范围来自 `foundation-compute` 的 `deploy/project.json`：

```text
region       cn-beijing
workspace_id 433673
resource_id  quota1uieq2yh4ie
```

PAI CLI 的持久化安装位置是
`/mnt/netdata/Team/Personal/ymc/.local/bin/pai`，配置目录是
`/mnt/netdata/Team/Personal/ymc/.config/aliyun-pai/cli`。

默认镜像和 1、2、4、8 GPU 资源比例来自
`deploy/templates/foundation-pytorch-preview.json`。Skill 采用 1 GPU、23 CPU、
225 GiB memory、225 GiB shared memory 作为默认 dry-run profile。用户显式传入
资源参数时覆盖该 profile。

## 提交模式

资源配额模式的最小参数是：

```text
--name
--command
--resource-id
--worker-count
--cpu
--memory
--gpu
--image
```

`--gpu-type` 只有在配额或服务端要求指定 GPU 型号时才添加。foundation-compute
模板没有登记固定 `gpu_type`，不能凭镜像名称猜测卡型。

按量 ECS 模式使用 `--worker-spec`。它与配额资源参数互斥：

```bash
pai dlc job submit \
  --name <name> \
  --image <image> \
  --command "<command>" \
  --worker-spec <ecs-instance-type> \
  --worker-count <count>
```

## 数据与代码

数据源可以重复传入：

```bash
--data-source d-xxxxxxxx:/mnt/data
--data-source uri=oss://bucket/path/,mount-path=/mnt/data,enable-cache=true
```

代码源使用 `--code-source`，需要时补充 `--code-branch`、`--code-commit` 和
`--code-mount-path`。如果代码已经在镜像中，启动命令应自行 `cd` 到正确目录。

## 认证

Skill 默认使用个人目录中的 owner-only 私密文件：

```text
ALIYUN_PAI_CREDENTIAL_ENV_FILE=/mnt/netdata/Team/Personal/ymc/.config/aliyun-pai/accesskey.env
```

文件已经创建，填写其中的 `PAI_ACCESS_KEY_ID` 和 `PAI_ACCESS_KEY_SECRET`。
如果运行环境需要切换凭证，可以在当前进程中显式设置
`ALIYUN_PAI_CREDENTIAL_ENV_FILE` 覆盖这个默认位置。

该文件可以包含：

```bash
PAI_ACCESS_KEY_ID=...
PAI_ACCESS_KEY_SECRET=...
```

也可以使用 foundation-compute 兼容的 JSON 文件：

```json
{
  "access_key_id": "...",
  "access_key_secret": "..."
}
```

JSON 文件必须是绝对路径、普通文件、当前用户拥有、权限不超过 0600，父目录不能
是符号链接或对其他用户可写。Skill 只把凭证放入 `pai` 子进程环境，不会打印。

## 资源余量

`resources` 实际调用：

```bash
pai resource quota get <quota-id> -o json
pai resource quota workloads <quota-id> --all-users --workload-type dlc -o json
```

配额详情中的 scheduled、dequeued、submitted、used、idle 和 total 代表不同口径。
Skill 保留原始 JSON，并在汇报时注明字段来源，不用 Submitted 减 Used 自行推导
空闲量。配额详情和排队任务是查询时快照，不能保证提交时仍有同样库存。

## 官方参考

- [PAI DLC job](https://www.alibabacloud.com/help/en/pai/developer-reference/dlc-distributed-training)
- [PAI CLI 配置与认证](https://help.aliyun.com/zh/pai/developer-reference/configuration-and-authentication)
- [PAI CLI 资源管理](https://help.aliyun.com/zh/pai/developer-reference/resource-management)
