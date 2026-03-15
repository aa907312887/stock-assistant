# Spec Kit 工作目录

本目录由 [Spec Kit](https://github.com/github/spec-kit) **init 已完成后**生成，用于规格驱动开发。

## 当前状态

- **Init 已完成**（AI 助手：Copilot，脚本类型：sh）。
- 可直接在 Cursor / Copilot 等 AI 对话中使用 Slash 命令。

## 目录说明

| 路径 | 说明 |
|------|------|
| `memory/constitution.md` | 项目宪法模板，可用 `/speckit.constitution` 填写原则 |
| `scripts/bash/` | Bash 自动化脚本（创建 feature、更新 context 等） |
| `templates/` | 规格、计划、任务、检查清单等模板 |
| `init-options.json` | 初始化时保存的选项（ai、script 等） |

## Slash 命令（在 AI 对话中使用）

1. **/speckit.constitution** — 设定项目原则  
2. **/speckit.specify** — 写功能规格  
3. **/speckit.clarify** — 澄清歧义（可选）  
4. **/speckit.plan** — 技术方案  
5. **/speckit.tasks** — 拆解任务  
6. **/speckit.implement** — 执行实现  

可选：**/speckit.analyze**、**/speckit.checklist**。

详见 [Spec Kit 文档](https://github.github.io/spec-kit/)。
