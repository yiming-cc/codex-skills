# 科研记录命令示例

`board` 表示 `python3 <skill目录>/scripts/board.py`。替换示例课题、任务 ID、路径和证据链接。

## 仅创建课题

用户只要求创建课题时，只配置项目并按资料编写课题说明，不执行下一节的任务创建命令。

```bash
board project-add "视觉表征研究"
board backlog doc create "视觉表征研究｜课题说明" --type specification --path projects/视觉表征研究 --plain
```

## 明确要求新增任务时

下列示例只适用于用户明确要求添加或拆分任务，不是创建课题的默认步骤。

```bash
board backlog task create "复现基线" --project "视觉表征研究" --description "运行用户指定的基线代码并记录复现情况。"
```

用户指定负责人时先从成员池匹配，再用返回的 `name`：

```bash
board members
board members "陈一鸣"
board backlog task edit TASK-123 --assignee "陈一鸣"
```

支持完整姓名、固定 ID 和已登记别名；未知姓名先确认，不猜测简称或 GitHub 身份。仅分配负责人不顺带改状态。知道真实截止日才添加 `--due-date YYYY-MM-DD`。

默认只润色用户的标题和 Description，不添加验收条件或拆分清单。仅当用户明确指定“验收项是保存运行配置和日志”时，才使用例如 `--ac "保存运行配置和日志"`；用户明确要求拆分时，也只写其要求范围内的条目。

## 开始、进展和核验

```bash
board backlog task edit TASK-123 --status "In Progress"
board backlog task edit TASK-123 --append-notes "2026-10-19：已完成两个随机种子；第三个尚在运行。证据：<真实结果链接>。下一步：补跑并核验数据划分。"
board backlog task edit TASK-123 --add-label blocked --append-notes "阻塞：等待数据访问；影响：暂时无法补跑。"
board backlog task edit TASK-123 --remove-label blocked
board backlog task edit TASK-123 --status Review
board backlog task edit TASK-123 --status Done --final-summary "运行及差异分析已核验，配置与结果见引用。"
```

存在用户指定的 AC 时才逐项核对/勾选；没有 AC 时不补写。科学结论与用户所指工作的实际完成情况分开记录。

## 文档

```bash
board backlog doc create "课题名称｜研究方案" --type specification --path projects/课题名称 --plain
board doc-write doc-123 /tmp/research-note.md
board backlog doc update doc-123 --tags "课题名称,研究方案"
board backlog task edit TASK-123 --add-doc "backlog/docs/实际文件.md"
```

课题说明按用户提供的内容写研究问题、背景、目标、已有基础和待明确事项。用户未要求时，不自行追加里程碑、任务关联、验收计划或排期。

实验记录写：目的、代码/data/config 版本、环境、实际结果、证据、结论边界、下一步。

周进展按项目概括实际变化，链接到任务和实验记录。口头计划和未获得的结果明确标为计划/待确认。

## 发布选定记录

```bash
board check
board publish --message "记录基线复现实验进展" --path backlog/tasks/实际文件.md --path backlog/docs/实际文件.md --path backlog.config.yml
board status
```

只传实际修改的文件。成员名单变更可指定 `--path members.json`；其他非记录文件用普通 Git 发布。命令不会强制覆盖 Git 历史。并发 push 最多自动重试一次；出现重复 ID 或冲突就停止、保留本地提交。
