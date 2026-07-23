# 项目记忆

这是项目本地 Memory Files 的唯一入口。它用于工作流导航、长期偏好和证据定位，不是当前项目事实的替代品。

处理需要项目历史、既有工作流、架构决策或长期偏好的任务时，先读取本文件和索引 topic 的 frontmatter，再只打开与用户请求最相关的正文。

## 硬规则

- memory 永远不能替代当前代码、配置、日志、checkpoint、指标或保存的运行 artifact。
- memory 与当前证据冲突时，以当前证据为准，并将对应记忆视为需要复核。
- 只有用户在当前请求中明确要求“记住”或“写入 memory”时，才能创建或修改记忆文档。
- 正式长期记忆只写入 `topics/`；`inbox/` 与 `dreams/` 在当前版本中不是权威来源。

## 检索协议

1. 读取本文件。
2. 批量读取下面索引文件的 frontmatter，不读取正文。
3. 用 `description`、正负触发词、状态和路径提示匹配用户请求；`paths` 不能单独触发加载。
4. 最多打开 1–3 个相关 topic 正文；`needs_review` 在使用前必须重新核验，`deprecated` 默认不加载。
5. 用 topic 选择工作流和证据路径。
6. 回答或修改前，从当前仓库文件或实际 artifact 核验关键事实。
7. 如果记忆与当前证据冲突，以当前证据为准。

## Topic 索引

## 更新策略

- 用户明确要求记录的长期规则，优先合并到同范围的现有 topic；没有合适 topic 时再新建。
- topic 文件名使用简洁、稳定、无日期的 `snake_case` 名称。
- topic 必须包含 `id`、`description`、`positive_triggers`、`negative_triggers`、`paths`、`status` 和 `last_verified` frontmatter；frontmatter 是机器可读路由元数据源。
- `paths` 只提供相关性提示，不能单独触发 topic；格式迁移不能推进 `last_verified` 日期。未经真实核验时使用 `status: needs_review` 与 `last_verified: null`。
- 只有可复用、有明确作用域、且不是临时运行状态的内容才能写入长期记忆。
- 正文只保留六节，不再创建 `范围` 或 `触发词` 章节。
- 新建、重命名或删除 topic 时，在同一变更中维护上面的文件索引；索引不复制路由元数据。
- topic 应保持适中长度，优先保存证据指针，不复制大段实现历史。
