---
name: project-setup
description: 在用户要求初始化或升级项目约定时，联动 manage-project-memory 建立项目记忆，并登记按需编写实验、验收和计划文档的规范。
---

# Project Setup

用户要求执行本技能的初始化或升级，即要求同时建立项目记忆并登记以下工作文档约定。无需用户再单独调用 `$manage-project-memory`。仅询问用法或要求预览时不写入目标项目。

## 工作文档约定

只有用户明确要求编写或更新工作文档时，才创建相应目录和文件。实验放入 `.agent/experiments/YYYY-MM-DD_<name>/`，计划放入 `.agent/plan/YYYY-MM-DD_<name>/`。同主题的后续记录沿用原目录。实验细节记录和验收文档分成两个文件，只要求其中一份时只写该份。完整约定见[记忆主题模板](assets/agent_work_documents.md)。

## 执行

1. 自动使用同级 [manage-project-memory](../manage-project-memory/SKILL.md)，按其要求读取记忆架构和目标仓库适用的 `AGENTS.md`。已有记忆时先检查入口和索引主题的 frontmatter。若同一规范已有主题，沿用其文件名并将缺少的约定合并到原文，保留项目专属细节。预览时只说明拟合并内容。
2. 从本技能目录调用初始化脚本，传入目标仓库路径。省略路径时使用当前工作目录。

```bash
python <project-setup目录>/scripts/setup_project.py /path/to/project
```

脚本直接调用 `manage-project-memory` 的初始化器和校验器。新项目采用 `.agent/memory/`，已有项目沿用声明的入口。遇到非标准入口写法时，按仓库声明传入 `--memory-root <仓库相对路径>`。同一规范已有其他文件名时，传入 `--topic topics/<已有文件名>.md`。脚本保留已有主题正文，在 `MEMORY.md` 登记硬规则和主题索引，在 `AGENTS.md` 保留记忆入口。预览使用 `--dry-run`。

3. 升级旧版布局时，脚本清理与旧模板完全一致的三份规范 README 和标准 `AGENTS.md` 文档说明。检查自定义说明和引用，把仍适用的文档约定合并到记忆，再调整已失效的引用。保留历史实验、计划和项目专属内容。
4. 核对记忆入口、规范主题和校验结果。若手动合并过规则，再运行依赖技能的校验器。初始化本身只建立记忆，不预建实验或计划目录。
