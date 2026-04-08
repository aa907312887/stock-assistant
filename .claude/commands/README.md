# Cursor 自定义 Slash 命令（Spec Kit）

本目录下的 `.md` 文件会在 Cursor 中输入 `/` 时作为可选命令出现。

## Spec Kit 命令列表

| 命令 | 说明 |
|------|------|
| `/speckit.constitution` | 设定项目宪法/原则 |
| `/speckit.specify` | 根据描述创建或更新功能规格 |
| `/speckit.clarify` | 澄清规格中的歧义 |
| `/speckit.plan` | 生成技术实现计划 |
| `/speckit.tasks` | 拆解为可执行任务 |
| `/speckit.implement` | 按任务执行实现 |
| `/speckit.analyze` | 跨制品一致性分析（可选） |
| `/speckit.checklist` | 生成质量检查清单（可选） |
| `/speckit.taskstoissues` | 将任务转为 issue（可选） |

以上内容来自 Spec Kit 模板（init 时按 `--ai copilot` 生成在 `.github/agents/`），已同步到此目录供 Cursor 识别。
