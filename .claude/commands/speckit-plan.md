---
description: Execute the implementation planning workflow using the plan template to generate design artifacts.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

**语言约定**：本命令生成的所有技术方案内容**一律使用中文**展示。plan.md、research.md、data-model.md、contracts/、quickstart.md 的章节标题、正文、列表、示例均使用中文；仅技术术语（如 API、CRON、JSON、HTTP）或专有名词（如 FastAPI、MySQL）可保留英文。不得整段使用英文描述设计。

**方案详细度要求**：技术方案必须达到**可直接按方案实现**的粒度，禁止仅写概要或一句话带过。
- **定时任务**：若功能涉及定时任务（如每日拉数、定时同步），必须明确写清：
  - 使用什么组件（如 APScheduler、cron、Celery 等）及在项目中的位置；
  - 如何注册（在应用启动的何处、何时注册，如 FastAPI lifespan 内）；
  - 调度策略（cron 表达式或具体时间，如「每日 17:00」）；
  - **部署时是否执行一次**（是/否，若「是」写清触发方式：应用启动后延迟 N 秒、或单独的管理接口/脚本）；
  - **是否提供手动触发方式**（HTTP 接口路径与方法、或管理命令、或脚本命令，以及鉴权方式）；
  - 失败与重试（失败是否重试、重试次数、日志与告警）。
- **接口与数据流**：写清请求路径、主要参数、响应结构、错误码或错误信息约定；数据从哪来到哪去、经哪些层。
- **数据模型**：表/实体、主键、关键字段与类型、索引、与现有表的关系。
- **前端与后端职责**：哪些逻辑在后端、哪些在前端，关键接口与页面一一对应。

1. **Setup**: Run `.specify/scripts/bash/setup-plan.sh --json` from repo root and parse JSON for FEATURE_SPEC, IMPL_PLAN, SPECS_DIR, BRANCH. For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").

2. **Load context**: Read FEATURE_SPEC and `.specify/memory/constitution.md`. Load IMPL_PLAN template (already copied).

3. **Execute plan workflow**: Follow the structure in IMPL_PLAN template to:
   - Fill Technical Context（**用中文**，未知项标「待澄清」）
   - Fill Constitution Check section from constitution
   - Evaluate gates (ERROR if violations unjustified)
   - **必须填写「关键设计详述」**（见模板），其中若涉及定时任务则必须完整填写「定时任务与部署设计」子节
   - Phase 0: Generate research.md（**中文**，resolve 所有待澄清）
   - Phase 1: Generate data-model.md, contracts/, quickstart.md（**中文**，达到可执行粒度）
   - Phase 1: Update agent context by running the agent script
   - Re-evaluate Constitution Check post-design

4. **Stop and report**: Command ends after Phase 2 planning. Report branch, IMPL_PLAN path, and generated artifacts.

## Phases

### Phase 0: Outline & Research

1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:

   ```text
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format（**中文**）:
   - 决策：[所选方案]
   - 理由：[为何选择]
   - 备选：[考虑过的其他方案及为何不采用]

**Output**: research.md（中文），所有待澄清已解决，结论可指导 Phase 1 设计

### Phase 1: Design & Contracts

**Prerequisites:** `research.md` complete

1. **Extract entities from feature spec** → `data-model.md`（**中文**）:
   - 实体名称、字段、类型、关系
   - 来自需求的校验规则
   - 若有状态则写清状态与流转

2. **Define interface contracts** (若项目有对外接口) → `/contracts/`（**中文**）:
   - 列出暴露给用户或其它系统的接口（路径、方法、主要参数、响应结构、错误约定）
   - 达到开发可直接按契约实现的粒度；若为 Web 服务则写清 endpoint、请求/响应示例
   - 纯内部脚本/工具可跳过

3. **Agent context update**:
   - Run `.specify/scripts/bash/update-agent-context.sh copilot`
   - These scripts detect which AI agent is in use
   - Update the appropriate agent-specific context file
   - Add only new technology from current plan
   - Preserve manual additions between markers

**Output**: data-model.md, /contracts/*, quickstart.md, agent-specific file

## Key rules

- Use absolute paths
- ERROR on gate failures or unresolved clarifications
