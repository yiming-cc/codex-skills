---
name: project-setup
description: 在用户要求初始化或升级项目约定时，联动 manage-project-memory 建立项目记忆，并初始化 Agent 的理解说明、实验和计划文档目录。
---

# Project Setup

用户要求执行本技能的初始化或升级，即要求同时建立项目记忆并登记以下工作文档约定。无需用户再单独调用 `$manage-project-memory`。仅询问用法或要求预览时不写入目标项目。

## 工作文档约定

初始化会建立 `.agent/doc/`、`.agent/experiments/` 和 `.agent/plan/` 三个基础目录，并写入各目录的用途说明。理解说明文档放入 `.agent/doc/`，用于记录可复用的架构、配置、流程和模块关系。实验放入 `.agent/experiments/YYYY-MM-DD_<name>/`，计划放入 `.agent/plan/YYYY-MM-DD_<name>/`。同主题的后续记录沿用原目录。实验细节记录和验收文档分成两个文件，只要求其中一份时只写该份。除初始化时的目录说明外，只有用户明确要求编写或更新工作文档时，才创建或更新具体内容。完整约定见[记忆主题模板](assets/agent_work_documents.md)。

## 执行

1. 自动使用同级 [manage-project-memory](../manage-project-memory/SKILL.md)，按其要求读取记忆架构和目标仓库适用的 `AGENTS.md`。已有记忆时先检查入口和索引主题的 frontmatter。若同一规范已有主题，沿用其文件名并将缺少的约定合并到原文，保留项目专属细节。预览时只说明拟合并内容。
2. 从本技能目录调用初始化脚本，传入目标仓库路径。省略路径时使用当前工作目录。

```bash
python <project-setup目录>/scripts/setup_project.py /path/to/project
```

脚本直接调用 `manage-project-memory` 的初始化器和校验器。新项目采用 `.agent/memory/`，已有项目沿用声明的入口。遇到非标准入口写法时，按仓库声明传入 `--memory-root <仓库相对路径>`。同一规范已有其他文件名时，传入 `--topic topics/<已有文件名>.md`。脚本保留已有主题正文，在 `MEMORY.md` 登记硬规则和主题索引，在 `AGENTS.md` 保留记忆入口。预览使用 `--dry-run`。

3. 升级旧版布局时，脚本清理与旧模板完全一致的三份规范 README 和标准 `AGENTS.md` 文档说明。检查自定义说明和引用，把仍适用的文档约定合并到记忆，再调整已失效的引用。保留历史实验、计划和项目专属内容。
4. 核对记忆入口、规范主题和校验结果。若手动合并过规则，再运行依赖技能的校验器。初始化同时创建三个基础工作文档目录及用途说明，不创建具体实验、计划或理解主题文档。
