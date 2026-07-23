---
id: <stable_snake_case_id>
description: "<一句话说明该 topic 在什么任务中相关>"
positive_triggers: ["<具体任务意图>"]
negative_triggers: ["<明确不应触发的相邻任务>"]
paths: []
status: needs_review
last_verified: null
---

# <Topic 名称>

## 稳定记忆

写入可复用的规则、偏好、职责边界或工作流约束。

## 检索提示

列出回答或修改前应检查的当前 repo 文件、artifact、日志、配置或命令。

## 证据引用

引用持久证据。优先使用 repo 文档、用户明确决策、已接受计划或保存的运行 artifact。

## 已知失败模式

记录反复发生过的错误及避免方式；没有已知模式时简短说明。

## 最近验证

核验后首个非空行以与 frontmatter 相同的 `YYYY-MM-DD` 开头，并说明核验对象和方式。尚未核验且 `last_verified: null` 时只说明待核验，不写日期前缀。

## 过期 / 不要推断

说明未经重新检查当前证据时不能泛化的事实。
