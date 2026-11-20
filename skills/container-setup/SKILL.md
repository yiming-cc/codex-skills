---
name: container-setup
description: 在 Linux 容器里初始化挂载的个人目录，将 HOME 中的 Codex、SSH、CLI 配置和公共 .bashrc 持久化，并让后续实例复用同一份环境。适用于首次迁移、接入已有个人盘或扩展持久化目录清单。
---

# 容器个人环境

从用户给出的挂载路径确定个人目录。个人目录必须已经存在，可以是挂载点的子目录。以需要配置 HOME 的用户运行。首次复制时，尽量选择相关程序没有写入配置或数据库的时段。

在交互式 Bash 中，从本 skill 的目录执行下列命令。将示例路径换成本次实例的个人目录。

```bash
source ./scripts/setup --personal /path/to/personal
```

需要预览时加 `--dry-run`。脚本依赖 Linux、Bash、Python 3 和 GNU coreutils。个人盘的 `setup` 是指向本 skill 脚本的相对软链。若从盘外引导，脚本会先把 skill 安装到个人盘的 `.codex/skills/container-setup`。替换旧入口时，原件备份到个人盘的 `.container-setup-backup-*/setup`。

下一台容器挂载个人盘后，在当前 Bash 执行以下命令。两个入口接受相同的选项。

```bash
source /path/to/personal/setup
```

初始化和钩子全部成功后，入口自动执行一次 `source ~/.bashrc`。用 `source` 调用入口时，PATH 和别名立即在当前 Bash 生效，可以直接运行 `codex --version`。直接执行入口时，配置加载到脚本的 Bash 子进程。`--dry-run` 和 `--help` 均跳过加载。

用户要求全部初始化时，加 `--all`。它执行默认初始化、个人盘的 `setup.d` 钩子和全部可选步骤。用 `--all --dry-run` 可先预览。

```bash
source /path/to/personal/setup --all
```

目前唯一的可选步骤是阿里云 PAI，也可以用 `--with-aliyun-pai` 单独启用。它在本次接入时持久化 `.config/aliyun-pai`，复用个人盘已有的匹配版本或下载安装 CLI，并在公共 `.bashrc` 设置 `PAI_CLI_BIN` 和 `PAI_CONFIG_DIR`。新容器需要 PAI 时也使用其中一个选项。

```bash
source /path/to/personal/setup --with-aliyun-pai
```

- 默认目录是 `.codex`、`.ssh`、`.config/gh`、`.local/bin`。个人盘缺项时，从 HOME 复制，双方都缺目录时创建空目录。整项已有时以个人盘为准。
- 首次复制时，指向上述清单内 HOME 路径的普通绝对软链会改成相对软链，便于下一台容器使用不同的 HOME。指向其他位置的软链保留原目标，跨容器使用时，该目标也需要可访问。
- 默认复用个人盘的 `.local/bin/codex`。如果入口缺失且个人盘已有 `.codex/packages/app-server-daemon/current/bin/codex`，脚本会为它创建相对软链。这样会随 `current` 切换版本，并保留同一安装包中的配套工具。容器的 CPU 架构需要与安装包匹配。
- `.bashrc` 单独处理。个人盘缺少它时，以当前 HOME 的版本为底稿。脚本在公共文件中维护 `container-setup` 配置段，将 `$HOME/.local/bin` 放在 PATH 首位。每个容器的 `~/.bashrc` 最终都链接到这份公共文件。
- HOME 中被替换的原件保存在该容器的 `~/.container-setup-backups/run-*/` 下。已接好的链接可重复执行。复制中断后可重跑，查看输出中的备份位置和失败路径。
- 用户要求调整目录时，编辑个人盘的 `setup.paths` 后重跑。每行一个相对 HOME 的目录，可用 `#` 写注释。目录之间不能嵌套。已有个人盘若要在首次运行时自定义清单，可先创建该文件。移除一行会停止管理该项，已经建立的链接仍可使用。
- 两个入口均按文件名顺序运行个人盘 `setup.d/` 下的 `*.sh` 和 `*.py`，第一个参数和工作目录都是个人目录。`25-pai-cli.sh` 只在显式启用 PAI 时运行。个人盘提供同名钩子时优先使用，否则使用 skill 附带的安装脚本。钩子应支持重复执行。
